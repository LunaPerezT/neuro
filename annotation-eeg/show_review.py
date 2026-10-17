"""Print compact review cards for datasets triaged as 'review' (batch by index range)."""

import json
import sys

start, end = int(sys.argv[1]), int(sys.argv[2])
profiles = [json.loads(l) for l in open("profiles.jsonl")]
review = [p for p in profiles if p["triage"] == "review"]
for i, p in enumerate(review[start:end], start):
    print(f"## [{i}] {p['id']} | N={p['n_rows'] or p['n_subjects_census']} | {(p['name'] or '')[:90]}")
    print(f"dx={p['dx_status']!r} domain={p['study_domain']!r} terms={p['readme_disease_terms'][:8]}")
    for c, info in p["group_columns"].items():
        vals = dict(list(info["values"].items())[:12])
        lv = info["levels"]
        lv = {k: str(v)[:40] for k, v in list(lv.items())[:10]} if lv else None
        print(f"  col {c!r}: {vals} miss={info['missing']}" + (f" levels={lv}" if lv else "") +
              (f" desc={info['description'][:80]!r}" if info["description"] else ""))
    if p["id_prefix_groups"]:
        print(f"  id_prefix: {p['id_prefix_groups']}")
    if not p["has_participants_tsv"]:
        print("  (no participants.tsv)")
    print(f"  readme: {p['readme_head'][:330]}")
print(f"\n{len(review)} datasets to review in total")
