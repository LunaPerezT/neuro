"""Shared helpers for the PC side of the pipeline: config, resumable state, downloads, brainlife CLI."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OPENNEURO_S3 = "https://s3.amazonaws.com/openneuro.org"

DEFAULTS = {
    "workdir": "~/neuro_adhd",             # downloads, staging, results (WSL home: fast and outside OneDrive)
    "brainlife_project": "",               # brainlife project id (24 hex chars) or exact name
    "priority_max": 1,                     # 1 = ADHD + controls; 2 = also other diagnoses of the same studies
    "datasets": ["ds000030", "ds005754", "ds007116", "ds007182", "ds008579"],
    "upload_batch": 8,                     # people per `bl bids upload` call
    "multiecho": "oc",                     # ds005754: "oc" = T2*-weighted optimal combination, "echo2" = middle echo
    "common_tr": 2.0,                      # every series is resampled to this TR before HOI metrics
    "bandpass": [0.01, 0.08],
    "fd_thresh": 0.5,                      # mm, Power FD; frames above are censored for the metrics
    "min_minutes": 4.0,                    # QC: minimum retained time
    "max_mean_fd": 0.5,                    # QC
    "matched_T": 120,                      # frames (at common_tr) for the T-matched O-information
    "keep_native_timeseries": True,        # keep the denoised parcel series (small) so nothing must be re-downloaded
}


def load_config(path: str | None = None) -> dict:
    cfg = dict(DEFAULTS)
    p = Path(path) if path else HERE / "config.json"
    if p.exists():
        cfg.update(json.loads(p.read_text()))
    cfg["workdir"] = Path(os.path.expanduser(cfg["workdir"]))
    for sub in ("staging", "tmp", "results", "logs", "cache", "atlas"):
        (cfg["workdir"] / sub).mkdir(parents=True, exist_ok=True)
    return cfg


def subjects(cfg) -> pd.DataFrame:
    S = pd.read_csv(REPO / "data/subjects.csv", dtype=str).fillna("")
    S["priority"] = S.priority.astype(int)
    return S[S.dataset_id.isin(cfg["datasets"]) & (S.priority >= 1) & (S.priority <= cfg["priority_max"])]


def files(cfg) -> pd.DataFrame:
    F = pd.read_csv(REPO / "data/files.csv", dtype=str).fillna("")
    F["bytes"] = F.bytes.astype(int)
    return F


class State:
    """Append-only JSON-lines log of finished steps: survives crashes, Ctrl+C and reboots."""

    def __init__(self, cfg, name):
        self.path = cfg["workdir"] / "logs" / f"{name}.jsonl"
        self.done = {}
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                try:
                    r = json.loads(line)
                    self.done[r["key"]] = r
                except (json.JSONDecodeError, KeyError):
                    pass

    def __contains__(self, key):
        return key in self.done and self.done[key].get("status") == "ok"

    def mark(self, key, status="ok", **info):
        r = {"key": key, "status": status, "time": time.strftime("%Y-%m-%d %H:%M:%S"), **info}
        self.done[key] = r
        with self.path.open("a") as f:
            f.write(json.dumps(r, default=str) + "\n")


def download(url: str, dest: Path, expected_bytes: int = 0, tries: int = 5) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and (not expected_bytes or dest.stat().st_size == expected_bytes):
        return dest
    part = dest.with_suffix(dest.suffix + ".part")
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(part, "wb") as f:
                shutil.copyfileobj(r, f, length=1 << 20)
            if expected_bytes and part.stat().st_size != expected_bytes:
                raise IOError(f"size {part.stat().st_size} != {expected_bytes}")
            part.replace(dest)
            return dest
        except Exception as e:  # network hiccups: retry with backoff
            if k == tries - 1:
                raise RuntimeError(f"download failed {url}: {e}") from e
            time.sleep(5 * (k + 1))


def openneuro_url(dataset: str, path: str) -> str:
    return f"{OPENNEURO_S3}/{dataset}/{path}"


def bl(*args, json_out=False, timeout=3600):
    """Run the brainlife CLI (installed with `npm install -g brainlife`)."""
    cmd = ["bl", *args] + (["--json"] if json_out else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    if json_out:
        out = r.stdout
        return json.loads(out[out.index("["):]) if "[" in out else []
    return r.stdout


def free_gb(path: Path) -> float:
    return shutil.disk_usage(path).free / 1e9
