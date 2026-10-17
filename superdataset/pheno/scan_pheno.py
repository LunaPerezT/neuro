"""For datasets flagged pheno_check: show phenotype/ and participants files with group/diagnosis-like columns."""
import re, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, "/home/claude/openneuro-mcp/src")
from openneuro_mcp.bids import parse_tsv
import rules_ext
X = Path("/home/claude/superdataset/meta/raw_extra")
KW = re.compile(r"(?i)(group|diag|dx|status|patient|control|cohort|clinical|condition|disorder|type|arm|case|hv|primary)")
ids = sys.argv[1:] or [d for d, v in rules_ext.R.items() if v.get("pheno_check")]
for ds in ids:
    files = [p for p in (X / ds).rglob("*") if p.is_file() and p.suffix in (".tsv", ".csv")] if (X / ds).exists() else []
    print(f"== {ds} files: {[str(f.relative_to(X/ds)) for f in files][:12]}")
    for f in files:
        try:
            cols, rows = parse_tsv(f.read_text(errors="replace")) if f.suffix == ".tsv" else (None, None)
        except Exception as e:
            continue
        if not cols:
            continue
        for c in cols:
            vals = Counter((r.get(c) or "").strip() for r in rows)
            if KW.search(c) and 1 < len(vals) <= 15:
                print(f"   {f.name}:{c}: {dict(vals.most_common(10))}")
