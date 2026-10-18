"""Per person: fetch preprocessed data -> parcellate + denoise -> censor -> common TR -> HOI metrics -> save
small results -> delete the downloads. Resumable: people already done are skipped.

Every study is preprocessed the same way (FreeSurfer 7.1.1 + fMRIPrep 20.2.3 on brainlife, bold in
MNI152NLin6Asym 2 mm + confounds + mask) and denoised here with the same code.

--xcpd-benchmark additionally analyses the GRMPY authors' own XCP-D series (ds008601, fMRIPrep 25 + XCP-D
linc, fsLR) into results/xcpd_benchmark/: an external check that our denoising gives the same connectome.

    python process.py                    # everyone available now; run again later for the rest
    python process.py --dataset ds008579 --limit 5
    python process.py --refresh          # re-query brainlife for newly finished fMRIPrep outputs
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

import denoise as D
import hoi_metrics as H
from common import State, bl, download, files, load_config, openneuro_url, subjects

DT_FUNC = "59b685a08e5d38b0b331ddc5"      # neuro/func/task
DT_REGRESS = "5c4f6a8af9109beac4b3dae0"   # neuro/regressors (fMRIPrep confounds)
DT_MASK = "5a281aee2c214c9ba83ce620"      # neuro/mask


def brainlife_index(cfg, refresh=False) -> dict:
    """subject -> {'bold': obj, 'regress': obj, 'mask': obj} for finished fMRIPrep tasks in the project."""
    cache = cfg["workdir"] / "cache" / "brainlife_outputs.json"
    if cache.exists() and not refresh and time.time() - cache.stat().st_mtime < 6 * 3600:
        objs = json.loads(cache.read_text())
    else:
        p = cfg["brainlife_project"]
        objs = {
            "bold": bl("data", "query", "-p", p, "-d", DT_FUNC, "--datatype_tag", "preprocessed", "-l", "10000", json_out=True),
            "regress": bl("data", "query", "-p", p, "-d", DT_REGRESS, "-l", "10000", json_out=True),
            "mask": bl("data", "query", "-p", p, "-d", DT_MASK, "--datatype_tag", "bold", "-l", "10000", json_out=True),
        }
        cache.write_text(json.dumps(objs))

    def task_of(o):
        prov = o.get("prov") or {}
        return prov.get("task_id") or (prov.get("task") or {}).get("_id")

    by_task = {}
    for kind, lst in objs.items():
        for o in lst:
            if o.get("status") != "stored" or o.get("removed"):
                continue
            by_task.setdefault(task_of(o), {})[kind] = o
    index = {}
    for t, d in by_task.items():
        if "bold" in d and "regress" in d and "rest" in d["bold"].get("datatype_tags", []):
            sub = str(d["bold"]["meta"].get("subject"))
            index.setdefault(sub, d)          # first finished run per person
    return index


def fetch_brainlife(cfg, objs, dest: Path) -> dict:
    out = {}
    for kind in ("bold", "regress", "mask"):
        if kind not in objs:
            continue
        d = dest / kind
        if not d.exists() or not any(d.iterdir()):
            bl("data", "download", "--id", objs[kind]["_id"], "--directory", str(d), timeout=3 * 3600)
        out[kind] = d
    bold = next(out["bold"].glob("*.nii.gz"))
    regress = out["regress"] / "regressors.tsv"
    mask = next(out["mask"].glob("*.nii.gz")) if "mask" in out else None
    return {"bold": bold, "regress": regress, "mask": mask}


def run_volume(cfg, row, paths, atlas):
    a_img, aff, labels, nets = atlas
    ts, coverage, tr_hdr = D.parcellate(paths["bold"], paths["mask"], a_img, aff)
    conf, fd, dummy = D.confounds_36p(paths["regress"])
    tr = float(row.tr) if row.tr else tr_hdr
    n0 = int(np.argmax(~dummy)) if dummy.any() else 0      # leading non-steady-state frames
    ts, conf, fd, dummy = ts[n0:], conf[n0:], fd[n0:], dummy[n0:]
    clean = D.clean(ts, conf, tr, cfg["bandpass"])
    return clean, fd, tr, coverage, {"n_dummy": n0}


def run_xcpd(cfg, row, F, tmp, atlas):
    _, _, labels, nets = atlas
    mine = F[(F.dataset_id == row.dataset_id) & (F.subject == row.subject) & (F.role == "xcpd")]
    got = {}
    for _, f in mine.iterrows():
        got[f.path] = download(openneuro_url(f.repo, f.path), tmp / Path(f.path).name, f.bytes)
    runs = sorted({p.split("_space-")[0].replace("_motion.tsv", "") for p in got})
    run = runs[0]   # first rest run (multiband)
    pick = lambda pat: next(v for k, v in got.items() if k.startswith(run) and pat in k)
    ts = D.xcpd_series(pick("seg-4S456Parcels"), pick("seg-Tian"), labels)
    fd = D.xcpd_fd(pick("_motion.tsv"))
    if len(fd) != len(ts):
        raise ValueError(f"motion ({len(fd)}) and series ({len(ts)}) lengths differ")
    tr = float(row.tr)
    return ts, fd, tr, np.isfinite(ts).all(0).astype(float), {"xcpd_run": Path(run).name}


def analyse(cfg, row, ts, fd, tr, coverage, extra, atlas, outdir: Path):
    _, _, labels, nets = atlas
    valid = D.censor_mask(fd, cfg["fd_thresh"])
    ts2, valid2 = D.to_common_tr(ts, valid, tr, cfg["common_tr"])
    ok_regions = np.isfinite(ts2).all(0)
    res = H.subject_metrics(ts2[:, ok_regions], valid2, nets[ok_regions], matched_T=cfg["matched_T"])
    # expand region-level outputs back to all 450 regions (NaN where the region had no coverage)
    full = lambda v: _expand(v, ok_regions)
    for k in list(res):
        v = res[k]
        if isinstance(v, np.ndarray) and v.ndim == 1 and len(v) == ok_regions.sum():
            res[k] = full(v)
        elif isinstance(v, np.ndarray) and v.ndim == 2 and v.shape == (ok_regions.sum(),) * 2:
            res[k] = _expand2(v, ok_regions)
    retained_min = valid2.sum() * cfg["common_tr"] / 60
    qc = {
        "dataset_id": row.dataset_id, "subject": row.subject, "global_id": row.global_id, "group": row.group,
        "source": row.source, "tr_native": tr, "n_native": len(ts), "mean_fd": float(np.mean(fd)),
        "frac_censored": float(1 - valid.mean()), "retained_minutes": float(retained_min),
        "n_regions_ok": int(ok_regions.sum()),
        "qc_pass": bool(retained_min >= cfg["min_minutes"] and np.mean(fd) <= cfg["max_mean_fd"] and ok_regions.sum() >= 430),
        **extra,
    }
    outdir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(outdir / "metrics.npz", labels=np.array(labels), networks=nets, region_ok=ok_regions,
                        coverage=coverage, **{k: v for k, v in res.items() if not isinstance(v, (str, dict))})
    if cfg["keep_native_timeseries"]:
        np.save(outdir / "timeseries_native.npy", ts.astype(np.float32))
        np.save(outdir / "fd_native.npy", fd.astype(np.float32))
    summary = {**qc, **{k: (float(v) if np.ndim(v) == 0 else None) for k, v in H.scalar_summary(res).items()}}
    (outdir / "qc.json").write_text(json.dumps(summary, indent=1, default=float))
    return summary


def run_benchmark(cfg, S, F, atlas):
    """Authors' XCP-D series for GRMPY -> same censoring/TR/metrics -> results/xcpd_benchmark/."""
    st = State(cfg, "xcpd_benchmark")
    have = set(F[F.role == "xcpd"].subject)
    csv = cfg["workdir"] / "results" / "xcpd_benchmark" / "summary.csv"
    for _, row in S[S.subject.isin(have) & S.dataset_id.isin(F[F.role == "xcpd"].dataset_id)].iterrows():
        key = f"{row.dataset_id}/{row.subject}"
        if key in st:
            continue
        tmp = cfg["workdir"] / "tmp" / f"xcpd_{row.subject}"
        try:
            ts, fd, tr, cov, extra = run_xcpd(cfg, row, F, tmp, atlas)
            out = cfg["workdir"] / "results" / "xcpd_benchmark" / row.dataset_id / f"sub-{row.subject}"
            summ = analyse(cfg, row, ts, fd, tr, cov, extra, atlas, out)
            pd.DataFrame([summ]).to_csv(csv, mode="a", header=not csv.exists(), index=False)
            st.mark(key)
            print(f"xcpd {key}")
        except Exception as e:
            st.mark(key, "error", error=str(e)[:500])
            print(f"xcpd FAIL {key}: {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def _expand(v, ok):
    out = np.full(len(ok), np.nan, dtype=float)
    out[ok] = v
    return out


def _expand2(m, ok):
    out = np.full((len(ok), len(ok)), np.nan, dtype=np.float32)
    out[np.ix_(ok, ok)] = m
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--dataset")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--keep-downloads", action="store_true")
    ap.add_argument("--xcpd-benchmark", action="store_true", help="also analyse the authors' XCP-D series of GRMPY")
    a = ap.parse_args()
    cfg = load_config(a.config)
    S = subjects(cfg)
    if a.dataset:
        S = S[S.dataset_id == a.dataset]
    F = files(cfg)
    st = State(cfg, "process")
    atlas = D.load_atlas(cfg["workdir"] / "atlas")
    if a.xcpd_benchmark:
        run_benchmark(cfg, S, F, atlas)
    index = {}
    if cfg["brainlife_project"]:
        index = brainlife_index(cfg, a.refresh)
    done = waiting = failed = 0
    summary_csv = cfg["workdir"] / "results" / "summary.csv"
    for _, row in S.iterrows():
        key = f"{row.dataset_id}/{row.subject}"
        if key in st:
            continue
        if a.limit and done >= a.limit:
            break
        if row.brainlife_subject not in index:
            waiting += 1
            continue
        tmp = cfg["workdir"] / "tmp" / f"{row.dataset_id}_{row.subject}"
        outdir = cfg["workdir"] / "results" / row.dataset_id / f"sub-{row.subject}"
        t0 = time.time()
        try:
            paths = fetch_brainlife(cfg, index[row.brainlife_subject], tmp)
            ts, fd, tr, cov, extra = run_volume(cfg, row, paths, atlas)
            extra["brainlife_bold_id"] = index[row.brainlife_subject]["bold"]["_id"]
            summ = analyse(cfg, row, ts, fd, tr, cov, extra, atlas, outdir)
            summ["seconds"] = round(time.time() - t0)
            pd.DataFrame([summ]).to_csv(summary_csv, mode="a", header=not summary_csv.exists(), index=False)
            st.mark(key, qc_pass=summ["qc_pass"], seconds=summ["seconds"])
            done += 1
            print(f"ok   {key:24s} {summ['seconds']:4d}s  FD {summ['mean_fd']:.2f}  {summ['retained_minutes']:.1f} min  "
                  f"O {summ.get('tri_oinfo_mean', float('nan')):+.4f}")
        except Exception as e:
            failed += 1
            st.mark(key, "error", error=f"{e}\n{traceback.format_exc()[-1500:]}")
            print(f"FAIL {key}: {e}")
        finally:
            if not a.keep_downloads:
                shutil.rmtree(tmp, ignore_errors=True)
    print(f"done {done} | waiting for brainlife {waiting} | failed {failed} | results in {cfg['workdir'] / 'results'}")


if __name__ == "__main__":
    main()
