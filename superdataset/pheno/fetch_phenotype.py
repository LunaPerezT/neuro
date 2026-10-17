"""Fetch phenotype/ files and top-level metadata (participants, README, CHANGES, *.tsv/*.json) for datasets.
Usage: python fetch_phenotype.py ids.txt  -> /home/claude/superdataset/meta/raw_extra/<ds>/..."""
import json, subprocess, sys, tempfile, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
OUT = Path("/home/claude/superdataset/meta/raw_extra")
MAXB = 5_000_000

def want(path):
    p = path.split("/")
    if p[0] == "phenotype" and path.endswith((".tsv", ".json", ".csv", ".txt", ".md")):
        return True
    return len(p) == 1 and (path.endswith((".tsv", ".json", ".md", ".txt", ".csv")) or path.upper().startswith(("README", "CHANGES")))

def run(ds):
    try:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--no-checkout",
                            f"https://github.com/OpenNeuroDatasets/{ds}.git", tmp + "/r"], check=True, capture_output=True, timeout=300)
            out = subprocess.run(["git", "-C", tmp + "/r", "ls-tree", "-r", "HEAD"], check=True, capture_output=True, text=True).stdout
        got = []
        for line in out.splitlines():
            meta, _, path = line.partition("\t")
            mode, typ, oid = meta.split()
            if not want(path) or mode == "120000":
                if want(path) and mode == "120000":
                    got.append(path + " (annexed:skip)")
                continue
            dest = OUT / ds / path
            if dest.exists():
                got.append(path); continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://raw.githubusercontent.com/OpenNeuroDatasets/{ds}/HEAD/" + urllib.request.quote(path)
            data = urllib.request.urlopen(url, timeout=60).read(MAXB + 1)
            if len(data) > MAXB:
                continue
            dest.write_bytes(data)
            got.append(path)
        return ds, got
    except Exception as e:
        return ds, [f"ERROR {type(e).__name__}: {e}"[:200]]

ids = [l.strip() for l in open(sys.argv[1]) if l.strip()]
status = {}
with ThreadPoolExecutor(12) as pool:
    for i, (ds, got) in enumerate(pool.map(run, ids), 1):
        status[ds] = got
        if i % 100 == 0:
            print(i, flush=True)
json.dump(status, open(OUT / "status.json", "w"), indent=0)
print("done", len(status), sum(1 for v in status.values() if v and v[0].startswith("ERROR")))
