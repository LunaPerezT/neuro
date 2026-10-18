"""End-to-end checks of the PC pipeline on synthetic data (no network needed if atlases are cached)."""
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import nibabel as nib
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import denoise as D  # noqa: E402
import process as P  # noqa: E402
from stage_upload import optimal_combination  # noqa: E402

ATLAS_CACHE = Path("/tmp/claude-0/atlas")


@pytest.fixture(scope="module")
def cfg(tmp_path_factory):
    wd = tmp_path_factory.mktemp("wd")
    (wd / "atlas").mkdir()
    for f in ATLAS_CACHE.glob("*"):
        shutil.copy(f, wd / "atlas" / f.name)
    shutil.copy(ATLAS_CACHE / "Schaefer400_7N.txt", wd / "atlas" / "Schaefer2018_400Parcels_7Networks_order.txt")
    from common import DEFAULTS
    c = dict(DEFAULTS); c["workdir"] = wd
    for s in ("results", "tmp", "logs", "cache"):
        (wd / s).mkdir(exist_ok=True)
    return c


@pytest.fixture(scope="module")
def atlas(cfg):
    return D.load_atlas(cfg["workdir"] / "atlas")


def test_atlas(atlas):
    img, aff, labels, nets = atlas
    assert img.max() == 450 and len(np.unique(img)) == 451 and len(labels) == 450
    assert set(nets) == {"Vis", "SomMot", "DorsAttn", "SalVentAttn", "Limbic", "Cont", "Default", "Subcortex"}


def synthetic_subject(atlas, tmp, T=80, tr=2.0, seed=0):
    img, aff, labels, nets = atlas
    rng = np.random.default_rng(seed)
    lat = rng.standard_normal((T, 8))
    region_sig = lat[:, rng.integers(0, 8, 450)] + rng.standard_normal((T, 450))
    motion = np.cumsum(0.05 * rng.standard_normal((T, 6)), 0)
    vol = np.zeros(img.shape + (T,), np.float32)
    lab = img
    idx = lab > 0
    vol[idx] = (100 + region_sig[:, lab[idx] - 1].T + 2 * motion[:, [0]].T).astype(np.float32)
    vol[idx] += 0.5 * rng.standard_normal((idx.sum(), T)).astype(np.float32)
    im = nib.Nifti1Image(vol, aff); im.header.set_zooms((2, 2, 2, tr))
    im.to_filename(str(tmp / "bold.nii.gz"))
    mask = (lab > 0).astype(np.uint8); mask[lab == 7] = 0       # one region outside the mask
    nib.Nifti1Image(mask, aff).to_filename(str(tmp / "mask.nii.gz"))
    conf = {n: motion[:, k] for k, n in enumerate(["trans_x", "trans_y", "trans_z", "rot_x", "rot_y", "rot_z"])}
    conf.update(white_matter=rng.standard_normal(T), csf=rng.standard_normal(T), global_signal=region_sig.mean(1))
    fd = np.r_[0, np.abs(np.diff(motion, axis=0)).sum(1)]
    fd[30:34] = 1.0
    conf["framewise_displacement"] = fd
    conf["non_steady_state_outlier00"] = np.r_[1, np.zeros(T - 1)]
    pd.DataFrame(conf).to_csv(tmp / "regressors.tsv", sep="\t", index=False)
    return {"bold": tmp / "bold.nii.gz", "mask": tmp / "mask.nii.gz", "regress": tmp / "regressors.tsv"}


def test_volume_pipeline_end_to_end(cfg, atlas, tmp_path):
    paths = synthetic_subject(atlas, tmp_path)
    row = SimpleNamespace(dataset_id="dsTEST", subject="01", global_id="NB0", group="ADHD", source="brainlife_upload", tr="2.0")
    ts, fd, tr, cov, extra = P.run_volume(cfg, row, paths, atlas)
    assert extra["n_dummy"] == 1 and ts.shape == (79, 450)
    assert np.isnan(ts[:, 6]).all() and cov[6] == 0          # region 7 masked out
    summ = P.analyse(cfg, row, ts, fd, tr, cov, extra, atlas, cfg["workdir"] / "results" / "dsTEST" / "sub-01")
    m = np.load(cfg["workdir"] / "results" / "dsTEST" / "sub-01" / "metrics.npz")
    assert m["fc"].shape == (450, 450) and np.isnan(m["fc"][6]).all()
    assert m["phiid_sts"].shape == (450, 450)
    assert summ["n_regions_ok"] == 449 and summ["frac_censored"] > 0
    json.loads((cfg["workdir"] / "results" / "dsTEST" / "sub-01" / "qc.json").read_text())


def test_common_tr_and_censor_mapping():
    T, tr = 400, 0.5
    t = np.arange(T) * tr
    ts = np.sin(2 * np.pi * 0.05 * t)[:, None].repeat(3, 1).astype(np.float32)
    valid = np.ones(T, bool); valid[100] = False
    out, v = D.to_common_tr(ts, valid, tr, 2.0)
    assert len(out) == 100 and v.sum() == 99 and not v[25]
    assert np.corrcoef(out[5:-5, 0], np.sin(2 * np.pi * 0.05 * np.arange(100) * 2.0)[5:-5])[0, 1] > 0.99


def test_xcpd_reorder(atlas, tmp_path):
    _, _, labels, _ = atlas
    T = 20
    rng = np.random.default_rng(0)
    cort = labels[:400]; tian = labels[400:]
    a = pd.DataFrame(rng.standard_normal((T, 456)), columns=cort + [f"extra{i}" for i in range(56)])
    a = a[list(reversed(a.columns))]                  # scrambled order
    t = pd.DataFrame(rng.standard_normal((T, 50)), columns=tian)
    a.to_csv(tmp_path / "a.tsv", sep="\t", index=False); t.to_csv(tmp_path / "t.tsv", sep="\t", index=False)
    X = D.xcpd_series(tmp_path / "a.tsv", tmp_path / "t.tsv", labels)
    assert X.shape == (T, 450) and np.allclose(X[:, 0], a[labels[0]]) and np.allclose(X[:, 449], t[labels[449]])


def test_optimal_combination(tmp_path):
    shape, T = (6, 6, 4), 10
    te = [0.0142, 0.0388, 0.0634]
    t2s, s0 = 0.04, 1000.0
    aff = np.eye(4)
    files = []
    for k, e in enumerate(te):
        d = np.full(shape + (T,), s0 * np.exp(-e / t2s), np.float32)
        f = tmp_path / f"e{k}.nii.gz"; nib.Nifti1Image(d, aff).to_filename(str(f)); files.append(f)
    optimal_combination(files, te, tmp_path / "oc.nii.gz")
    oc = np.asarray(nib.load(str(tmp_path / "oc.nii.gz")).dataobj)
    w = np.array([e * np.exp(-e / t2s) for e in te]); w /= w.sum()
    expected = (w * s0 * np.exp(-np.array(te) / t2s)).sum()
    assert np.allclose(oc, expected, rtol=1e-4)
