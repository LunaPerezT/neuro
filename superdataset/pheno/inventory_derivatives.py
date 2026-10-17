"""Subjects whose imaging/electrophysiology exists only under derivatives/ (or sourcedata/), per dataset.
Output: /home/claude/superdataset/inventory/derivative_subjects.csv (dataset_id, subject, datatypes, location)"""
import csv, re, subprocess, sys, tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
csv.field_size_limit(10**9)
DT = {"anat", "func", "dwi", "fmap", "perf", "eeg", "meg", "ieeg", "pet", "beh", "nirs", "motion", "micr", "emg"}
EXT = re.compile(r"\.(nii(\.gz)?|edf|bdf|set|fdt|vhdr|eeg|fif|con|sqd|mefd|nwb|snirf|mgz|gii|dlabel\.nii|mat)$")
raw = defaultdict(set)
for r in csv.DictReader(open("/home/claude/superdataset/inventory/subjects.csv")):
    raw[r["dataset_id"]].add(r["subject"])

def run(ds):
    try:
        with tempfile.TemporaryDirectory() as t:
            subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--no-checkout",
                            f"https://github.com/OpenNeuroDatasets/{ds}.git", t + "/r"], check=True, capture_output=True, timeout=600)
            out = subprocess.run(["git", "-C", t + "/r", "ls-tree", "-r", "--name-only", "HEAD"], check=True,
                                 capture_output=True, text=True, timeout=600).stdout
    except Exception as e:
        return ds, None
    found = defaultdict(set)
    for path in out.splitlines():
        parts = path.split("/")
        if parts[0] not in ("derivatives", "sourcedata") or not EXT.search(path):
            continue
        sub = next((p[4:] for p in parts if p.startswith("sub-")), None)
        if not sub or sub in raw[ds]:
            continue
        dt = next((p for p in reversed(parts[:-1]) if p in DT), None)
        if dt is None:
            m = re.search(r"_(bold|T1w|T2w|dwi|eeg|meg|ieeg|pet)\b", parts[-1])
            dt = {"bold": "func", "T1w": "anat", "T2w": "anat"}.get(m.group(1), m.group(1)) if m else "other"
        found[sub].add((dt, parts[0]))
    return ds, found

ids = [l.strip() for l in open(sys.argv[1]) if l.strip()]
with open("/home/claude/superdataset/inventory/derivative_subjects.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["dataset_id", "subject", "datatypes", "location"])
    with ThreadPoolExecutor(12) as pool:
        for i, (ds, found) in enumerate(pool.map(run, ids), 1):
            for sub, items in sorted((found or {}).items()):
                w.writerow([ds, sub, ";".join(sorted({d for d, _ in items})), ";".join(sorted({l for _, l in items}))])
            if i % 200 == 0:
                print(i, flush=True); f.flush()
print("done")
