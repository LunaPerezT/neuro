"""Compact review cards for non-EEG datasets triaged 'review'. Usage: python cards.py START END"""

import json
import re
import sys

eeg = {r["id"] for r in json.load(open("/home/claude/eeg-annotation/census_eeg.json"))}
ps = [json.loads(l) for l in open("profiles.jsonl")]
rev = sorted((p for p in ps if p["triage"] == "review" and p["id"] not in eeg), key=lambda p: -p["n_subjects_census"])
start, end = int(sys.argv[1]), int(sys.argv[2])
for i, p in enumerate(rev[start:end], start):
    head = f"[{i}] {p['id']} N={p['n_rows'] or p['n_subjects_census']} | {(p['name'] or '')[:70]}"
    meta = f" dx={p['dx_status']!r} dom={(p['study_domain'] or '')[:40]!r} t={p['readme_disease_terms'][:5]}"
    print(head + meta)
    dx = []
    for c, info in p["group_columns"].items():
        vals = info["values"]
        if re.match(r"(?i)dx_", c) or (set(map(str, vals)) <= {"0", "1"} and len(p["group_columns"]) > 6):
            if not c.lower().endswith("_remit"):
                dx.append(f"{c}({vals.get('1', vals.get(1, 0))})")
            continue
        if len(vals) > 8 and not info.get("levels"):
            print(f"   {c}: <{len(vals)} values>")
            continue
        lv = info.get("levels") or {}
        shown = ", ".join(f"{v}{'=' + str(lv[v])[:22] if v in lv else ''}:{n}" for v, n in list(vals.items())[:8])
        print(f"   {c}: {shown}" + (f" miss={info['missing']}" if info["missing"] else ""))
    if dx:
        print("   binary: " + " ".join(dx))
    if p["id_prefix_groups"]:
        print(f"   prefix: {dict(list(p['id_prefix_groups'].items())[:8])}")
    rm = re.sub(r"^#?\s*(README|Readme)\s*", "", p["readme_head"])
    print(f"   > {rm[:260]}")
print(f"-- {len(rev)} total")
