"""Stage a few people at a time from OpenNeuro and upload them to the brainlife project, then delete them.

Only the files fMRIPrep needs are downloaded: one T1w, the first resting-state run and its fieldmap
(about 0.15-0.6 GB per person). People are relabelled with their global person ID (NB...), so the five
studies can share one brainlife project without ID clashes. Re-running skips everyone already uploaded.

    python stage_upload.py                # all pending people (priority from config.json)
    python stage_upload.py --dataset ds005754 --limit 10
    python stage_upload.py --dry-run      # stage only, do not upload or delete
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
from pathlib import Path

import nibabel as nib
import numpy as np

from common import REPO, State, bl, download, files, free_gb, load_config, openneuro_url, subjects

SKIP_KEYS = {"IntendedFor", "B0FieldIdentifier", "B0FieldSource"}
# ds005754's sidecars give EchoTime=0.0422 for all three echoes; the true values are in its README
ECHO_TIMES = {"ds005754": [0.0148, 0.0284, 0.0420]}


def echo_times(ds, metas):
    tes = [float(m["EchoTime"]) for m in metas]
    if len(set(tes)) < len(tes):
        if ds not in ECHO_TIMES:
            raise ValueError(f"{ds}: identical EchoTime in every echo sidecar and no override")
        tes = ECHO_TIMES[ds]
    return tes


def load_sidecars():
    with gzip.open(REPO / "data/sidecars.jsonl.gz", "rt") as f:
        rows = [json.loads(l) for l in f]
    return {(r["dataset_id"], r["path"]): r["meta"] for r in rows}


def optimal_combination(echo_files: list[Path], tes: list[float], out: Path):
    """T2*-weighted combination of multi-echo BOLD (Posse et al. 1999), voxelwise log-linear T2* fit
    on the time-averaged signal. Runs before motion correction: echoes are simultaneous so share motion."""
    imgs = [nib.load(str(f)) for f in echo_files]
    data = np.stack([np.asarray(i.dataobj, dtype=np.float32) for i in imgs])          # E,X,Y,Z,T
    te = np.asarray(tes, float)[:, None, None, None]
    mean = data.mean(-1)
    ok = (mean > 0).all(0)
    logS = np.log(np.where(mean > 0, mean, 1.0))
    te_c = te - te.mean(0)
    slope = ((te_c * (logS - logS.mean(0))).sum(0)) / (te_c ** 2).sum(0)          # = -1/T2*
    t2s = np.where(ok & (slope < 0), -1.0 / np.minimum(slope, -1e-6), np.nan)
    t2s = np.clip(np.nan_to_num(t2s, nan=te.max()), 0.25 * te.min(), 2.0)             # seconds
    w = te * np.exp(-te / t2s)
    w = w / w.sum(0, keepdims=True)
    comb = (w[..., None] * data).sum(0).astype(np.float32)
    comb[~ok] = 0
    hdr = imgs[1].header.copy()
    hdr.set_data_dtype(np.float32)
    nib.Nifti1Image(comb, imgs[1].affine, hdr).to_filename(str(out))


def stage_person(cfg, row, F, sidecars, root: Path):
    ds, sub, nb = row.dataset_id, row.subject, row.brainlife_subject
    mine = F[(F.dataset_id == ds) & (F.subject == sub)]
    raw = cfg["workdir"] / "tmp" / f"raw_{ds}_{sub}"
    got = {}
    for _, f in mine[mine.role.isin(["t1w", "bold", "fmap"])].iterrows():
        if f.path.endswith(".json"):
            continue
        got[f.path] = download(openneuro_url(ds, f.path), raw / f.path, f.bytes)
    sdir = root / f"sub-{nb}"
    for d in ("anat", "func", "fmap"):
        (sdir / d).mkdir(parents=True, exist_ok=True)

    def side(path, extra=None, drop=()):
        meta = {k: v for k, v in sidecars.get((ds, path), {}).items() if k not in drop}
        meta.update(extra or {})
        return meta

    t1 = [p for p in mine[mine.role == "t1w"].path if p.endswith(".nii.gz")][0]
    shutil.move(got[t1], sdir / "anat" / f"sub-{nb}_T1w.nii.gz")
    (sdir / "anat" / f"sub-{nb}_T1w.json").write_text(json.dumps(side(t1), indent=1))

    bolds = sorted(p for p in mine[mine.role == "bold"].path if p.endswith(".nii.gz"))
    bold_out = sdir / "func" / f"sub-{nb}_task-rest_bold.nii.gz"
    if len(bolds) > 1:
        tes = echo_times(ds, [side(b) for b in bolds])
        if cfg["multiecho"] == "oc":
            optimal_combination([got[b] for b in bolds], tes, bold_out)
            meta = side(bolds[1], {"MultiEchoCombination": f"T2*-weighted optimal combination of TE={tes}"}, drop={"EchoTime"} | SKIP_KEYS)
        else:
            shutil.move(got[bolds[1]], bold_out)
            meta = side(bolds[1], {"EchoTime": tes[1], "EchoNote": "middle echo only"}, drop=SKIP_KEYS)
    else:
        shutil.move(got[bolds[0]], bold_out)
        meta = side(bolds[0], drop=SKIP_KEYS)
    meta.setdefault("TaskName", "rest")
    (sdir / "func" / bold_out.name.replace(".nii.gz", ".json")).write_text(json.dumps(meta, indent=1))

    for p in sorted(x for x in mine[mine.role == "fmap"].path if x.endswith(".nii.gz")):
        m = side(p, drop=SKIP_KEYS)
        m["IntendedFor"] = f"func/sub-{nb}_task-rest_bold.nii.gz"
        suffix = Path(p).name[: -len(".nii.gz")].rsplit("_", 1)[-1]     # epi, phasediff, magnitude1/2, fieldmap...
        if suffix == "epi":
            direc = {"j": "PA", "j-": "AP", "i": "LR", "i-": "RL"}.get(m.get("PhaseEncodingDirection", ""), "X")
            name = f"sub-{nb}_dir-{direc}_epi"
        else:
            name = f"sub-{nb}_{suffix}"
        shutil.move(got[p], sdir / "fmap" / f"{name}.nii.gz")
        (sdir / "fmap" / f"{name}.json").write_text(json.dumps(m, indent=1))
    shutil.rmtree(raw, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--dataset")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-fmap", action="store_true", help="upload without fieldmaps (fMRIPrep then uses SyN-SDC)")
    a = ap.parse_args()
    cfg = load_config(a.config)
    if not cfg["brainlife_project"] and not a.dry_run:
        raise SystemExit("Set brainlife_project in config.json first")
    S = subjects(cfg)
    S = S[S.source == "brainlife_upload"]
    if a.dataset:
        S = S[S.dataset_id == a.dataset]
    F = files(cfg)
    if a.no_fmap:
        F = F[F.role != "fmap"]
    sidecars = load_sidecars()
    st = State(cfg, "upload")
    todo = [r for _, r in S.iterrows() if f"{r.dataset_id}/{r.subject}" not in st]
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(todo)} people to upload")
    for b in range(0, len(todo), cfg["upload_batch"]):
        batch = todo[b: b + cfg["upload_batch"]]
        if free_gb(cfg["workdir"]) < 5:
            raise SystemExit("Less than 5 GB free: stopping")
        root = cfg["workdir"] / "staging" / f"batch_{b // cfg['upload_batch']:03d}"
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True)
        (root / "dataset_description.json").write_text(json.dumps(
            {"Name": "ADHD HOI pilot (subset of OpenNeuro studies)", "BIDSVersion": "1.8.0", "DatasetType": "raw"}))
        staged = []
        for r in batch:
            try:
                stage_person(cfg, r, F, sidecars, root)
                staged.append(r)
                print(f"  staged {r.dataset_id} {r.subject} -> sub-{r.brainlife_subject}")
            except Exception as e:  # keep going; the person is retried next run
                st.mark(f"{r.dataset_id}/{r.subject}", "error", error=str(e)[:500])
                print(f"  ERROR {r.dataset_id} {r.subject}: {e}")
        if a.dry_run or not staged:
            print(f"dry run: staged in {root}")
            continue
        tags = sorted({"adhd-hoi"} | {r.dataset_id for r in staged})
        args = ["bids", "upload", "-d", str(root), "-p", cfg["brainlife_project"]]
        for t in tags:
            args += ["-t", t]
        out = bl(*args, timeout=6 * 3600)
        (cfg["workdir"] / "logs" / f"{root.name}_upload.log").write_text(out)
        for r in staged:
            st.mark(f"{r.dataset_id}/{r.subject}", brainlife_subject=r.brainlife_subject, batch=root.name)
        shutil.rmtree(root, ignore_errors=True)
        print(f"uploaded batch {root.name} ({len(staged)} people)")


if __name__ == "__main__":
    main()
