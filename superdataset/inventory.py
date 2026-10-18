"""Build a file-level BIDS inventory for OpenNeuro datasets without downloading data.

For each dataset: shallow, blob-less clone of github.com/OpenNeuroDatasets/<id> (tree only),
then parse every BIDS path into entities. Outputs (inventory/):
  recordings.csv  one row per data file: dataset, subject, session, datatype, task, acq, run, suffix, extension
  subjects.csv    one row per dataset subject with the datatypes/modalities present (multimodal matrix)
  status.json     clone status per dataset
Usage: python inventory.py ids.txt [workers]
"""

import csv
import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OUT = Path(__file__).resolve().parent / "inventory"
DATA_EXT = (".nii", ".nii.gz", ".edf", ".bdf", ".set", ".fdt", ".vhdr", ".eeg", ".fif", ".ds", ".con", ".sqd",
            ".mefd", ".nwb", ".snirf", ".mat", ".tsv.gz", ".gii", ".dlabel.nii", ".mgz", ".tif", ".png")
ENTITY_RE = re.compile(r"(?:^|_)(sub|ses|task|acq|run|rec|dir|echo|space|desc|mod|ce|trc|recording)-([A-Za-z0-9]+)")
DATATYPES = {"anat", "func", "dwi", "fmap", "perf", "eeg", "meg", "ieeg", "pet", "beh", "nirs", "motion", "micr", "emg"}


def list_tree(ds: str, workdir: Path) -> list[str]:
    dest = workdir / ds
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--no-checkout",
                    f"https://github.com/OpenNeuroDatasets/{ds}.git", str(dest)],
                   check=True, capture_output=True, timeout=600)
    # "<mode> <type> <oid>\t<path>": for git-annex symlinks the blob oid is a hash of the annex key,
    # which itself contains the SHA256 of the file content -> identical oids = identical recordings.
    out = subprocess.run(["git", "-C", str(dest), "ls-tree", "-r", "HEAD"],
                         check=True, capture_output=True, text=True, timeout=600).stdout
    subprocess.run(["rm", "-rf", str(dest)])
    entries = []
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        mode, _, oid = meta.split(" ")
        entries.append((path, oid, mode))
    return entries


def parse(ds: str, path: str, oid: str = "", mode: str = "") -> dict | None:
    parts = path.split("/")
    if not parts[0].startswith("sub-") or len(parts) < 2:
        return None
    name = parts[-1]
    datatype = next((p for p in reversed(parts[:-1]) if p in DATATYPES), None)
    if datatype is None:
        return None
    base = name
    ext = ""
    for e in sorted(DATA_EXT, key=len, reverse=True):
        if name.endswith(e):
            base, ext = name[: -len(e)], e
            break
    if not ext:  # sidecars (.json, events.tsv, channels.tsv) are metadata, not recordings
        return None
    ents = dict(ENTITY_RE.findall(base))
    suffix = base.rsplit("_", 1)[-1] if "_" in base else base
    return {"dataset_id": ds, "subject": ents.get("sub") or parts[0][4:], "session": ents.get("ses", ""),
            "datatype": datatype, "task": ents.get("task", ""), "acq": ents.get("acq", ""), "run": ents.get("run", ""),
            "suffix": suffix, "extension": ext, "path": path, "oid": oid, "annexed": mode == "120000"}


def process(ds: str, workdir: Path) -> tuple[str, list[dict], str]:
    try:
        paths = list_tree(ds, workdir)
    except Exception as exc:  # noqa: BLE001
        return ds, [], f"error: {type(exc).__name__}"
    rows = [r for p, oid, mode in paths if (r := parse(ds, p, oid, mode))]
    return ds, rows, f"ok:{len(paths)} files"


def main() -> None:
    ids = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    OUT.mkdir(exist_ok=True)
    status, all_rows = {}, []
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(process, ds, Path(tmp)) for ds in ids]
        for i, fut in enumerate(as_completed(futures), 1):
            ds, rows, st = fut.result()
            status[ds] = st
            all_rows += rows
            if i % 100 == 0:
                print(f"{i}/{len(ids)} done", flush=True)
    fields = ["dataset_id", "subject", "session", "datatype", "task", "acq", "run", "suffix", "extension", "path", "oid", "annexed"]
    with open(OUT / "recordings.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)
    subj = defaultdict(lambda: {"datatypes": set(), "sessions": set(), "tasks": set(), "n_files": 0})
    for r in all_rows:
        s = subj[(r["dataset_id"], r["subject"])]
        s["datatypes"].add(r["datatype"])
        if r["session"]:
            s["sessions"].add(r["session"])
        if r["task"]:
            s["tasks"].add(r["task"])
        s["n_files"] += 1
    with open(OUT / "subjects.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dataset_id", "subject", "datatypes", "n_datatypes", "sessions", "tasks", "n_files"])
        for (ds, sub), s in sorted(subj.items()):
            w.writerow([ds, sub, ";".join(sorted(s["datatypes"])), len(s["datatypes"]), ";".join(sorted(s["sessions"])),
                        ";".join(sorted(s["tasks"]))[:500], s["n_files"]])
    json.dump(status, open(OUT / "status.json", "w"), indent=1)
    print(f"datasets {len(status)} | ok {sum(v.startswith('ok') for v in status.values())} | "
          f"data files {len(all_rows)} | subjects {len(subj)}")


if __name__ == "__main__":
    main()
