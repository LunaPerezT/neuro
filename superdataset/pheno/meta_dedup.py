"""Metadata-based duplicate candidates (complements content-hash dedup): identical README openings,
identical (age, sex) multisets in participants.tsv, identical dataset names. Output: out/metadata_duplicate_candidates.csv"""
import csv, hashlib, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, "/home/claude/openneuro-mcp/src")
from openneuro_mcp.bids import parse_tsv
ROOT = Path("/home/claude/superdataset")
census = {r["id"]: r for r in json.load(open(ROOT / "census_all.json"))}
ids = [l.strip() for l in open(ROOT / "ids_human.txt") if l.strip()]
inv = Counter(r["dataset_id"] for r in csv.DictReader(open(ROOT / "inventory/subjects.csv")))
keys = defaultdict(lambda: defaultdict(list))
for ds in ids:
    base = ROOT / "meta" / "raw_extra" / ds
    if not base.exists():
        base = ROOT / "meta" / "raw" / ds
    rd = next((p for p in base.glob("README*")), None) if base.exists() else None
    if rd:
        t = re.sub(r"\W+", " ", rd.read_text(errors="replace")).lower()
        t = re.sub(r"openneuro curator note.*?considerations", "", t)
        if len(t) > 200:
            keys["readme"][hashlib.md5(t[:600].encode()).hexdigest()].append(ds)
    pt = base / "participants.tsv" if base.exists() else None
    if pt and pt.exists():
        cols, rows = parse_tsv(pt.read_text(errors="replace"))
        lc = {c.lower(): c for c in cols}
        a, s = lc.get("age"), lc.get("sex") or lc.get("gender")
        if a and len(rows) >= 8:
            ms = sorted(f"{(r.get(a) or '').strip()}|{(r.get(s) or '').strip().lower()[:1] if s else ''}" for r in rows)
            if len({m for m in ms}) > 3:
                keys["age_sex"][hashlib.md5("\n".join(ms).encode()).hexdigest()].append(ds)
    name = re.sub(r"\W+", " ", (census.get(ds, {}).get("name") or "")).lower().strip()
    if len(name) > 12 and not name.startswith(("todo", "unnamed", "ds0")):
        keys["name"][name].append(ds)
pairs = defaultdict(set)
for kind, groups in keys.items():
    for g in groups.values():
        for i in range(len(g)):
            for j in range(i + 1, len(g)):
                pairs[(g[i], g[j])].add(kind)
with open(ROOT / "pheno/out/metadata_duplicate_candidates.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["dataset_a", "dataset_b", "evidence", "n_a", "n_b", "name_a", "name_b"])
    for (a, b), ev in sorted(pairs.items()):
        w.writerow([a, b, ";".join(sorted(ev)), inv[a], inv[b], (census[a].get("name") or "")[:60], (census[b].get("name") or "")[:60]])
print(len(pairs), Counter(";".join(sorted(v)) for v in pairs.values()))
