"""Add SNOMED-coded condition table and SQLite database to pheno/out."""
import csv, json, sqlite3
from collections import Counter
from pathlib import Path
OUT = Path("out")
csv.field_size_limit(10**9)
snomed = json.load(open("conditions_snomed.json"))
labels = json.load(open(OUT / "condition_labels.json"))
P = list(csv.DictReader(open(OUT / "participants.csv")))
used = Counter(p["condition"] for p in P if p["counted"] == "True")
with open(OUT / "conditions.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["condition", "label", "snomed_code", "snomed_term", "snomed_match", "counted_rows"])
    for k in sorted(labels):
        s = snomed.get(k, {})
        w.writerow([k, labels[k], s.get("snomed_code", ""), s.get("snomed_term", ""), s.get("snomed_match", ""), used.get(k, 0)])
db = OUT / "neuro_openneuro.sqlite"
db.unlink(missing_ok=True)
con = sqlite3.connect(db)
for name in ("participants", "datasets", "ranking", "conditions", "metadata_duplicate_candidates"):
    rows = list(csv.DictReader(open(OUT / f"{name}.csv")))
    cols = list(rows[0].keys())
    con.execute(f"CREATE TABLE {name} ({', '.join(chr(34)+c+chr(34) for c in cols)})")
    con.executemany(f"INSERT INTO {name} VALUES ({','.join('?'*len(cols))})", [tuple(r[c] for c in cols) for r in rows])
con.execute("CREATE INDEX ix_p_gid ON participants(global_id)")
con.execute("CREATE INDEX ix_p_cond ON participants(condition)")
con.execute("CREATE INDEX ix_p_ds ON participants(dataset_id)")
con.commit()
print({t: con.execute(f"select count(*) from {t}").fetchone()[0] for t in ("participants", "datasets", "ranking", "conditions")})
