"""Peek at participants.tsv columns and distinct values for given datasets. Usage: python peek.py ds1 ds2 ..."""
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, "/home/claude/openneuro-mcp/src")
from openneuro_mcp.bids import parse_tsv
RAW = Path("/home/claude/superdataset/meta/raw")
for ds in sys.argv[1:]:
    p = RAW / ds / "participants.tsv"
    if not p.exists():
        print(f"== {ds}: no participants.tsv; files: {[f.name for f in (RAW/ds).iterdir()] if (RAW/ds).exists() else '-'}")
        continue
    cols, rows = parse_tsv(p.read_text(errors="replace"))
    print(f"== {ds}: {len(rows)} rows")
    for c in cols:
        vals = Counter((r.get(c) or "").strip() for r in rows)
        if len(vals) <= 12:
            print(f"   {c}: {dict(vals.most_common(12))}")
        else:
            print(f"   {c}: <{len(vals)}> e.g. {[v for v, _ in vals.most_common(5)]}")
    ids = [r.get('participant_id', '') for r in rows]
    print(f"   ids: {ids[:4]} ... {ids[-3:]}")
