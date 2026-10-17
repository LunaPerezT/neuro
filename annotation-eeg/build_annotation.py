"""Apply the annotation rules to every EEG dataset and write the participant-level database.

Outputs (in out/):
  participants.csv  one row per person per dataset with condition, role, source and confidence
  datasets.csv      one row per dataset with annotation summary, cohort, duplicate and caution flags
  conditions.csv    condition vocabulary with SNOMED CT codes (if conditions_snomed.json exists)
  ranking.csv       conditions ranked by unique participants, with and without within-dataset controls
  neuro_eeg.sqlite  the same tables in SQLite
"""

import csv
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, "/home/claude/openneuro-mcp/src")
from openneuro_mcp.bids import NA_VALUES, parse_tsv  # noqa: E402

from rules import CONDITIONS, R  # noqa: E402

RAW, OUT = Path("raw"), Path("out")
NON_PATIENT = {"HEALTHY", "PRESUMED_HEALTHY", "NOT_REPORTED", "MIXED_COMMUNITY", "ANIMAL", "PHANTOM"}
EXCLUDED_CONDS = {"ANIMAL", "PHANTOM"}


def auto_rule(row: dict, profile: dict) -> dict:
    species = (row.get("species") or "").lower()
    if species and "human" not in species:
        return {"cond": "ANIMAL", "conf": "high", "note": f"Species: {row.get('species')}", "auto": True}
    if "phantom" in species:
        return {"cond": "PHANTOM", "conf": "high", "exclude": True, "auto": True}
    if profile["triage"] == "auto_healthy":
        return {"cond": "HEALTHY", "conf": "high", "note": "OpenNeuro dxStatus = Healthy / Control.", "auto": True}
    return {"cond": "PRESUMED_HEALTHY", "conf": "low",
            "note": "No clinical labels in participants.tsv, dxStatus or README; presumed non-clinical volunteers.", "auto": True}


def first_col(cols: list[str], names: tuple[str, ...]) -> str | None:
    lower = {c.lower(): c for c in cols}
    return next((lower[n] for n in names if n in lower), None)


def to_float(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def label(rule: dict, r: dict, pid: str) -> tuple[str, str, str]:
    """Return (condition, raw_value, source) for one participant."""
    if "derive" in rule:
        d = rule["derive"]
        val = to_float(r.get(d["col"], ""))
        if val is None:
            return "NOT_REPORTED", r.get(d["col"], ""), f"derive:{d['col']}(missing)"
        return (d["above"] if val >= d["threshold"] else d["below"]), str(val), f"derive:{d['col']}>={d['threshold']}"
    if "col" in rule:
        raw = (r.get(rule["col"]) or "").strip()
        cond = rule["map"].get(raw)
        if cond is None:  # tolerate case differences
            cond = {k.lower(): v for k, v in rule["map"].items()}.get(raw.lower(), "NOT_REPORTED")
        return cond, raw, f"column:{rule['col']}"
    if rule.get("prefix"):
        m = re.match(rule.get("prefix_regex", r"^sub-([A-Za-z]+)"), pid)
        raw = m.group(1).lower() if m else ""
        return rule["map"].get(raw, "NOT_REPORTED"), raw, "subject_id_prefix"
    if "id_map" in rule:
        m = re.match(rule["person_regex"], pid)
        key = m.group(1) if m else pid
        return rule["id_map"].get(key, rule["default"]), key, "readme_id_list"
    return rule["cond"], "", "dataset_level"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    census = {r["id"]: r for r in json.load(open("census_eeg.json"))}
    profiles = {json.loads(l)["id"]: json.loads(l) for l in open("profiles.jsonl")}
    subjects = json.load(open("subjects_eeg.json")) if Path("subjects_eeg.json").exists() else {}

    # identical participants.tsv files (>= 5 rows) point to the same people
    hashes: dict[str, list[str]] = defaultdict(list)
    for ds in census:
        p = RAW / ds / "participants.tsv"
        if p.exists() and profiles[ds]["n_rows"] >= 5 and len(profiles[ds]["columns"]) >= 2:
            hashes[hashlib.sha256(p.read_bytes().strip()).hexdigest()].append(ds)
    same_file = {ds: sorted(g) for g in hashes.values() if len(g) > 1 for ds in g}

    participants, datasets = [], []
    for ds, row in census.items():
        prof = profiles[ds]
        rule = R.get(ds) or auto_rule(row, prof)
        dup_of = rule.get("dup_of")
        tsv = RAW / ds / "participants.tsv"
        cols, rows = parse_tsv(tsv.read_text(errors="replace")) if tsv.exists() else ([], [])
        listed = bool(rows)
        with_data = subjects.get(ds)  # subjects that actually have EEG files (OpenNeuro validator)
        n_tsv_without_data = 0
        if with_data is not None:
            have = {x.lower() for x in with_data}
            kept = [r for r in rows if r.get("participant_id", "").lower().removeprefix("sub-") in have]
            n_tsv_without_data = len(rows) - len(kept)
            known = {r.get("participant_id", "").lower().removeprefix("sub-") for r in kept}
            rows = kept + [{"participant_id": f"sub-{x}", "_not_in_tsv": "1"} for x in with_data if x.lower() not in known]
        elif not rows:  # no participants.tsv and no subject list: placeholders for OpenNeuro's count
            rows = [{"participant_id": f"unlisted-{i + 1:04d}", "_not_in_tsv": "1"} for i in range(row["n_subjects"])]
        age_c = first_col(cols, ("age", "age_years", "age (years)", "ages"))
        sex_c = first_col(cols, ("sex", "gender", "biological_sex"))
        seen_people: set[str] = set()
        ds_rows = []
        for r in rows:
            pid = r.get("participant_id", "")
            person = pid
            if rule.get("person_col"):
                person = f"{rule['person_col']}={r.get(rule['person_col'], pid)}"
            elif rule.get("person_regex"):
                m = re.match(rule["person_regex"], pid)
                person = m.group(1) if m else pid
            if person in seen_people:
                continue
            seen_people.add(person)
            cond, raw, source = ("NOT_REPORTED", "", "duplicate_dataset") if dup_of else label(rule, r, pid)
            ds_rows.append({
                "dataset_id": ds, "participant_id": pid, "person_key": person, "condition": cond,
                "raw_label": raw, "label_source": source, "confidence": rule.get("conf", "low"),
                "age": to_float(r.get(age_c, "")) if age_c else None,
                "sex": (r.get(sex_c, "") or "").strip()[:12] if sex_c else "",
                "in_participants_tsv": not r.get("_not_in_tsv"),
            })
        has_patients = any(p["condition"] not in NON_PATIENT for p in ds_rows)
        for p in ds_rows:
            if p["condition"] == "HEALTHY":
                p["role"] = "control" if has_patients else "healthy"
            elif p["condition"] in NON_PATIENT:
                p["role"] = {"PRESUMED_HEALTHY": "presumed_healthy", "NOT_REPORTED": "unknown", "MIXED_COMMUNITY": "mixed_community"}.get(p["condition"], "excluded")
            else:
                p["role"] = "patient"
        excluded_reason = (f"duplicate of {dup_of}" if dup_of else rule.get("flag") if rule.get("exclude") else
                           "non-human or phantom" if rule.get("cond") in EXCLUDED_CONDS else "")
        conds = Counter(p["condition"] for p in ds_rows)
        datasets.append({
            "dataset_id": ds, "name": row["name"], "url": row["url"], "n_people": len(ds_rows),
            "subject_list": "openneuro_validator" if with_data is not None else "participants_tsv",
            "n_tsv_rows_without_eeg": n_tsv_without_data,
            "n_subjects_openneuro": row["n_subjects"], "modalities": ";".join(row["modalities"]),
            "tasks": ";".join(row["tasks"][:12]), "dx_status_openneuro": row.get("dx_status") or "",
            "species": row.get("species") or "", "paper_doi": row.get("paper_doi") or "",
            "size_gb": round((row.get("size_bytes") or 0) / 1e9, 2),
            "conditions": ";".join(f"{k}:{v}" for k, v in conds.most_common()),
            "has_patients": has_patients, "has_controls": has_patients and conds.get("HEALTHY", 0) > 0,
            "annotation": "auto" if rule.get("auto") else "expert_rule", "confidence": rule.get("conf", "low"),
            "cohort": rule.get("cohort") or (dup_of and R.get(dup_of, {}).get("cohort"))
                      or (f"same_file:{same_file[ds][0]}" if ds in same_file else ds),
            "overlap_group": rule.get("group") or (dup_of and R.get(dup_of, {}).get("group")) or "",
            "duplicate_of": dup_of or "", "same_participants_file_as": ";".join(d for d in same_file.get(ds, []) if d != ds),
            "excluded_reason": excluded_reason or "", "caution": rule.get("flag", "") if not rule.get("exclude") else "",
            "intervention": rule.get("intervention", ""), "note": rule.get("note", ""),
        })
        for p in ds_rows:
            p["counted"] = not excluded_reason
        participants += ds_rows

    snomed = json.load(open("conditions_snomed.json")) if Path("conditions_snomed.json").exists() else {}
    conditions = [{"condition": k, "label": v, **snomed.get(k, {})} for k, v in CONDITIONS.items()]

    # ranking: unique people per condition, collapsing datasets of the same cohort (max per cohort)
    ds_by_id = {d["dataset_id"]: d for d in datasets}
    def bound(level: str, controls_only: bool = False) -> dict[str, int]:
        per = defaultdict(lambda: defaultdict(Counter))
        for p in participants:
            d = ds_by_id[p["dataset_id"]]
            if p["counted"] and (not controls_only or d["has_controls"]):
                key = d["overlap_group"] or d["cohort"] if level == "group" else d["cohort"]
                per[p["condition"]][key][p["dataset_id"]] += 1
        return {c: sum(max(x.values()) for x in g.values()) for c, g in per.items()}, per

    upper, per_cohort = bound("cohort")
    lower, per_group = bound("group")
    lower_ctrl, _ = bound("group", controls_only=True)
    upper_ctrl, _ = bound("cohort", controls_only=True)
    ranking = []
    for cond in upper:
        ranking.append({"condition": cond, "label": CONDITIONS[cond],
                        "unique_people_min": lower[cond], "unique_people_max": upper[cond],
                        "with_controls_min": lower_ctrl.get(cond, 0) if cond not in NON_PATIENT else None,
                        "with_controls_max": upper_ctrl.get(cond, 0) if cond not in NON_PATIENT else None,
                        "independent_groups": len(per_group[cond]), "cohorts": len(per_cohort[cond]),
                        "datasets": sum(len(c) for c in per_cohort[cond].values()),
                        "snomed_code": snomed.get(cond, {}).get("snomed_code")})
    ranking.sort(key=lambda r: (r["condition"] in NON_PATIENT, -r["unique_people_min"], -r["unique_people_max"]))

    def write(name: str, rows: list[dict]) -> None:
        with open(OUT / f"{name}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    for name, rows in (("participants", participants), ("datasets", datasets), ("conditions", conditions), ("ranking", ranking)):
        write(name, rows)
    db = sqlite3.connect(OUT / "neuro_eeg.sqlite")
    for name, rows in (("participants", participants), ("datasets", datasets), ("conditions", conditions), ("ranking", ranking)):
        cols = list(rows[0].keys())
        db.execute(f"DROP TABLE IF EXISTS {name}")
        db.execute(f"CREATE TABLE {name} ({', '.join(cols)})")
        db.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})",
                       [tuple(r.get(c) for c in cols) for r in rows])
    db.commit()
    db.close()
    json.dump({ds: {k: v for k, v in r.items()} for ds, r in R.items()}, open(OUT / "annotation_rules.json", "w"), indent=1, ensure_ascii=False)

    counted = [p for p in participants if p["counted"]]
    print(f"datasets {len(datasets)} | participant rows {len(participants)} | counted {len(counted)}")
    print("roles:", Counter(p["role"] for p in counted).most_common())
    print("excluded datasets:", sum(1 for d in datasets if d["excluded_reason"]))
    print("unmapped values:", Counter((p['dataset_id'], p['raw_label']) for p in participants if p['condition'] == 'NOT_REPORTED' and p['label_source'].startswith(('column', 'subject'))).most_common(10))
    print("identical participants.tsv groups:", sorted({tuple(g) for g in same_file.values()}))
    print()
    for r in ranking:
        print(f"{r['condition']:<20} people={r['unique_people_min']:>6}-{r['unique_people_max']:<6} with_ctrl={r['with_controls_min']!s:>5}-{r['with_controls_max']!s:<5} groups={r['independent_groups']:>3} datasets={r['datasets']:>3}")


if __name__ == "__main__":
    main()
