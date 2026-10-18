"""Progress overview: per dataset, how many people are uploaded, preprocessed on brainlife, analysed, failed.

    python status.py            # uses the cached brainlife listing (refreshed every 6 h)
    python status.py --refresh
"""
import argparse

import pandas as pd

from common import State, load_config, subjects
from process import brainlife_index


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--config"); ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    cfg = load_config(a.config)
    S = subjects(cfg)
    up, pr = State(cfg, "upload"), State(cfg, "process")
    idx = brainlife_index(cfg, a.refresh) if cfg["brainlife_project"] else {}
    key = S.dataset_id + "/" + S.subject
    S = S.assign(
        uploaded=[k in up or src != "brainlife_upload" for k, src in zip(key, S.source)],
        fmriprep_ready=[b in idx for b in S.brainlife_subject],
        analysed=[k in pr for k in key],
        failed=[k in pr.done and pr.done[k]["status"] == "error" for k in key],
        qc_pass=[bool(pr.done.get(k, {}).get("qc_pass")) for k in key],
    )
    t = S.groupby(["dataset_id", "group"])[["uploaded", "fmriprep_ready", "analysed", "failed", "qc_pass"]].sum()
    t.insert(0, "people", S.groupby(["dataset_id", "group"]).size())
    print(t.to_string())
    print("\nTOTAL", t.sum().to_dict())
    errs = [(k, v.get("error", "")[:160].splitlines()[0]) for k, v in pr.done.items() if v["status"] == "error"]
    if errs:
        print("\nlast errors:"); [print(" ", k, e) for k, e in errs[-10:]]


if __name__ == "__main__":
    main()
