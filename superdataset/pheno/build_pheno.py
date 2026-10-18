"""Phenotype annotation of every participant in every human OpenNeuro dataset, all modalities.

Inputs
  inventory/subjects.csv        subjects with data files and their datatypes (from inventory.py)
  linked/people.csv             global person ids (content-hash linking, link_people.py)
  meta/raw, meta/raw_extra      participants.tsv / phenotype files per dataset
  meta/profiles.jsonl           triage per dataset
  eeg-annotation/rules.py       expert rules for EEG datasets (v1)
  pheno/rules_ext.py            expert rules for all other reviewed datasets

Outputs (pheno/out/)
  participants.csv   one row per (dataset, subject) with data: global id, modalities, condition, role, provenance
  datasets.csv       one row per dataset: rule summary, cohort/overlap, duplicate/derivative, flags
  ranking.csv        condition x modality: unique people (lower/upper bounds), datasets
"""

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10**9)
ROOT = Path("/home/claude/superdataset")
sys.path.insert(0, "/home/claude/openneuro-mcp/src")
sys.path.insert(0, "/home/claude/eeg-annotation")
sys.path.insert(0, str(ROOT / "pheno"))
from openneuro_mcp.bids import parse_tsv  # noqa: E402
import rules as eeg_rules  # noqa: E402
import rules_ext  # noqa: E402

OUT = ROOT / "pheno" / "out"
NON_PATIENT = {"HEALTHY", "PRESUMED_HEALTHY", "NOT_REPORTED", "MIXED_COMMUNITY", "ANIMAL", "PHANTOM", "UNRESOLVED"}
EXCLUDED_CONDS = {"ANIMAL", "PHANTOM"}
MODALITY = {"anat": "MRI", "func": "fMRI", "dwi": "dMRI", "fmap": None, "perf": "ASL", "eeg": "EEG", "meg": "MEG",
            "ieeg": "iEEG", "pet": "PET", "nirs": "fNIRS", "beh": None, "motion": "motion", "emg": "EMG", "micr": "microscopy"}
CONDITIONS = {**eeg_rules.CONDITIONS, **rules_ext.NEW_CONDITIONS}


def load_rules() -> dict:
    rules = {ds: dict(r, _src="eeg_v1") for ds, r in eeg_rules.R.items()}
    for ds, r in rules_ext.R.items():
        rules[ds] = dict(r, _src="ext_v1")
    for ds, link in getattr(rules_ext, "LINKS", {}).items():
        rules.setdefault(ds, {}).update(link)
    return rules


def auto_rule(profile: dict, census_row: dict) -> dict:
    species = (census_row.get("species") or "").lower()
    if species and "human" not in species:
        return {"cond": "ANIMAL", "conf": "high", "_src": "auto"}
    if profile and profile.get("triage") == "auto_healthy":
        return {"cond": "HEALTHY", "conf": "high", "note": "OpenNeuro dxStatus = Healthy / Control.", "_src": "auto"}
    return {"cond": "PRESUMED_HEALTHY", "conf": "low", "_src": "auto",
            "note": "No clinical labels in participants.tsv, dxStatus or README."}


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def lookup(mapping: dict, raw: str):
    if raw in mapping:
        return mapping[raw]
    return {str(k).lower(): v for k, v in mapping.items()}.get(raw.lower())


def label(rule: dict, r: dict, pid: str) -> tuple[str, str, str]:
    default = rule.get("default", "NOT_REPORTED")
    if "derive" in rule:
        d = rule["derive"]
        val = to_float(r.get(d["col"], ""))
        if val is None:
            return "NOT_REPORTED", r.get(d["col"], ""), f"derive:{d['col']}(missing)"
        return (d["above"] if val >= d["threshold"] else d["below"]), str(val), f"derive:{d['col']}>={d['threshold']}"
    if "col" in rule:
        raw = (r.get(rule["col"]) or "").strip()
        if raw.lower() in ("n/a", "na", "nan"):
            raw = ""
        cond = lookup(rule.get("map", {}), raw)
        return (cond or default), raw, f"column:{rule['col']}"
    if rule.get("prefix"):
        m = re.match(rule.get("prefix_regex", r"^sub-([A-Za-z]+)"), pid, re.I)
        raw = m.group(1).lower() if m else ""
        return rule["map"].get(raw, default), raw, "subject_id_prefix"
    if "id_map" in rule:
        m = re.match(rule["person_regex"], pid)
        key = m.group(1) if m else pid
        return rule["id_map"].get(key, rule["default"]), key, "readme_id_list"
    return rule.get("cond", "NOT_REPORTED"), "", "dataset_level"


def secondary(rule: dict, r: dict) -> list[str]:
    out = []
    for col, mapping in (rule.get("multi") or {}).items():
        raw = (r.get(col) or "").strip()
        cond = lookup(mapping, raw) if raw else None
        if cond and cond not in out:
            out.append(cond)
    return out


def read_participants(ds: str) -> tuple[list[str], list[dict]]:
    for base in (ROOT / "meta" / "raw_extra", ROOT / "meta" / "raw"):
        p = base / ds / "participants.tsv"
        if p.exists():
            try:
                return parse_tsv(p.read_text(errors="replace"))
            except Exception:  # noqa: BLE001
                continue
    return [], []


def canon(x: str) -> str:
    x = re.sub(r"[^a-z0-9]", "", x.lower().removeprefix("sub-"))
    return re.sub(r"(?<![0-9])0+(?=[0-9])", "", x)  # drop leading zeros of every number


def first_col(cols, names):
    lower = {c.lower(): c for c in cols}
    return next((lower[n] for n in names if n in lower), None)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    census = {r["id"]: r for r in json.load(open(ROOT / "census_all.json"))}
    human = [l.strip() for l in open(ROOT / "ids_human.txt") if l.strip()]
    nonhuman_extra = set(json.load(open(ROOT / "linked" / "excluded_nonhuman_extra.json")))
    profiles = {}
    for line in open(ROOT / "meta" / "profiles.jsonl"):
        p = json.loads(line)
        profiles[p["id"]] = p
    rules = load_rules()

    subjects = defaultdict(dict)  # ds -> {subject: datatypes}
    for r in csv.DictReader(open(ROOT / "inventory" / "subjects.csv")):
        subjects[r["dataset_id"]][r["subject"]] = r["datatypes"].split(";")
    deriv = defaultdict(dict)  # subjects whose files exist only under derivatives/ or sourcedata/
    dpath = ROOT / "inventory" / "derivative_subjects.csv"
    if dpath.exists():
        for r in csv.DictReader(open(dpath)):
            deriv[r["dataset_id"]][r["subject"]] = [t for t in r["datatypes"].split(";") if t != "other"]
    gid = {(r["dataset_id"], r["subject"]): r["global_id"] for r in csv.DictReader(open(ROOT / "linked" / "people.csv"))}

    participants, datasets = [], []
    for ds in human:
        row = census.get(ds, {})
        rule = rules.get(ds) or {}
        if not any(k in rule for k in ("cond", "col", "prefix", "id_map", "derive")):
            rule = {**auto_rule(profiles.get(ds), row), **rule}
        if ds in nonhuman_extra:
            rule = {"cond": "ANIMAL", "conf": "high", "_src": "nonhuman_list"}
        cols, rows = read_participants(ds)
        by_id = {}
        for r in rows:
            key = (r.get("participant_id") or "").strip().lower().removeprefix("sub-")
            if key:
                by_id.setdefault(key, r)
                by_id.setdefault("~" + canon(key), r)
        subs = dict(subjects.get(ds) or {})
        location = {s: "raw" for s in subs}
        for s, dt in deriv.get(ds, {}).items():
            if s not in subs:
                subs[s], location[s] = dt, "derivatives_only"
        if not subs:  # inventory failed: fall back to participants.tsv rows
            subs = {k: [] for k in by_id if not k.startswith("~")}
            location = {k: "participants_tsv_only" for k in subs}
        age_c = first_col(cols, ("age", "age_years", "age (years)", "ages", "age_at_scan"))
        sex_c = first_col(cols, ("sex", "gender", "biological_sex"))
        replaced = rule.get("dup_of") or rule.get("derivative_of")
        extra = {}  # phenotype-file columns merged into participant rows
        for rel in rule.get("pheno_files", []):
            path = ROOT / "meta" / "raw_extra" / (rel if rel.startswith("ds") else f"{ds}/{rel}")
            if path.exists():
                _, prow = parse_tsv(path.read_text(errors="replace"))
                for pr in prow:
                    k = canon((pr.get("participant_id") or "").strip())
                    extra.setdefault(k, {}).update({c: v for c, v in pr.items() if c != "participant_id"})
        ds_rows = []
        for sub, dtypes in sorted(subs.items()):
            r = dict(by_id.get(sub.lower()) or by_id.get("~" + canon(sub)) or {})
            matched_pheno = canon(sub) in extra
            r.update(extra.get(canon(sub), {}))
            pid = f"sub-{sub}"
            if replaced and not rules.get(replaced):
                cond, raw, source = label(rule, r, pid) if ("cond" in rule or "col" in rule) else ("NOT_REPORTED", "", "derivative")
            elif replaced:
                cond, raw, source = label(rules[replaced], r, pid) if r else (rules[replaced].get("cond", "NOT_REPORTED"), "", f"inherited:{replaced}")
            else:
                cond, raw, source = label(rule, r, pid)
            others = secondary(rule, r) if r else []
            if rule.get("pheno_files") and not matched_pheno and rule.get("cond_unmatched"):
                cond, source = rule["cond_unmatched"], "phenotype_file(missing)"
            elif rule.get("pheno_files") and matched_pheno:
                source += "+phenotype_file"
            if others and (cond == "HEALTHY" or (rule.get("multi_primary") and cond in ("UNRESOLVED", "TRANSDIAGNOSTIC", "NOT_REPORTED"))):
                cond, others = others[0], others[1:]
            others = [o for o in others if o != cond]
            mods = sorted({MODALITY.get(t, t) for t in dtypes if MODALITY.get(t, t)})
            ds_rows.append({
                "dataset_id": ds, "subject": sub, "global_id": gid.get((ds, sub), ""),
                "modalities": ";".join(mods), "condition": cond, "other_conditions": ";".join(others),
                "raw_label": raw, "label_source": source, "confidence": rule.get("conf", "low"),
                "age": to_float(r.get(age_c, "")) if age_c else None,
                "sex": (r.get(sex_c, "") or "").strip()[:12] if sex_c else "",
                "in_participants_tsv": bool(r), "data_location": location.get(sub, ""), "rule_source": rule.get("_src", ""),
            })
        has_patients = any(p["condition"] not in NON_PATIENT for p in ds_rows)
        excluded_reason = (f"duplicate of {rule['dup_of']}" if rule.get("dup_of") else
                           f"derivative of {rule['derivative_of']}" if rule.get("derivative_of") else
                           "non-human or phantom" if rule.get("cond") in EXCLUDED_CONDS else
                           (rule.get("flag") or "excluded") if rule.get("exclude") else "")
        cohort = rule.get("cohort") or ""
        overlap = rule.get("overlap") or rule.get("group") or ""
        for p in ds_rows:
            c = p["condition"]
            p["role"] = ("control" if has_patients else "healthy") if c == "HEALTHY" else {
                "PRESUMED_HEALTHY": "presumed_healthy", "NOT_REPORTED": "unknown", "MIXED_COMMUNITY": "mixed_community",
                "UNRESOLVED": "unresolved", "ANIMAL": "excluded", "PHANTOM": "excluded"}.get(c, "patient")
            p["counted"] = not excluded_reason and p["role"] != "excluded"
            p["cohort"], p["overlap_group"] = cohort, overlap
            p["unit"] = rule.get("split") or ds  # releases of one study split by subject count as one dataset
        participants += ds_rows
        cond_counts = Counter(p["condition"] for p in ds_rows)
        datasets.append({
            "dataset_id": ds, "name": (row.get("name") or "")[:120], "modalities": ";".join(row.get("modalities") or []),
            "n_subjects_with_data": len(ds_rows), "rule_source": rule.get("_src", ""), "confidence": rule.get("conf", ""),
            "conditions": ";".join(f"{k}:{v}" for k, v in cond_counts.most_common()),
            "study_condition": rule.get("study_cond", ""), "published_counts": json.dumps(rule.get("counts") or {}) if rule.get("counts") else "",
            "cohort": cohort, "overlap_group": overlap, "duplicate_of": rule.get("dup_of", ""),
            "derivative_of": rule.get("derivative_of", ""), "excluded_reason": excluded_reason,
            "caution": rule.get("flag", "") if not rule.get("exclude") else "", "intervention": rule.get("intervention", ""),
            "needs_phenotype_check": bool(rule.get("pheno_check")), "note": rule.get("note", ""),
        })

    link_cohorts_by_id(participants)
    participants, datasets = drop_structural_only(participants, datasets)
    write(OUT / "participants.csv", participants)
    write(OUT / "datasets.csv", datasets)
    ranking = rank(participants, datasets)
    write(OUT / "ranking.csv", ranking)
    json.dump(CONDITIONS, open(OUT / "condition_labels.json", "w"), indent=1, ensure_ascii=False)
    counted = [p for p in participants if p["counted"]]
    print(f"datasets {len(datasets)} | rows {len(participants)} | counted {len(counted)} | "
          f"unique people {len({p['global_id'] or p['dataset_id'] + p['subject'] for p in counted})}")
    print("roles:", Counter(p["role"] for p in counted).most_common())
    unknown = sorted({p["condition"] for p in participants} - set(CONDITIONS))
    print("conditions without label:", unknown)


# Techniques for which a structural MRI of the same person is useful (registration, head/source
# models, electrode or optode localisation, attenuation correction, tractography).
OTHER_TECHNIQUES = {"fMRI", "dMRI", "ASL", "EEG", "MEG", "iEEG", "PET", "fNIRS"}


def drop_structural_only(participants: list[dict], datasets: list[dict]) -> tuple[list[dict], list[dict]]:
    """Remove structural MRI that no other technique of the same person can use.

    A person's structural MRI is kept when that person (global id, i.e. across all datasets) has data
    from any OTHER_TECHNIQUES. Rows whose only data is structural MRI for a person without any other
    technique are removed; datasets left without rows are removed. Everything removed is listed in
    removed_structural_only.csv so the decision can be audited or reverted."""
    person_mods = defaultdict(set)
    for p in participants:
        person_mods[p["global_id"]].update(filter(None, p["modalities"].split(";")))
    keep, removed = [], []
    for p in participants:
        mods = set(filter(None, p["modalities"].split(";")))
        if "MRI" in mods and not (person_mods[p["global_id"]] & OTHER_TECHNIQUES):
            removed.append(p)
        else:
            keep.append(p)
    left = Counter(p["dataset_id"] for p in keep)
    gone = Counter(p["dataset_id"] for p in removed)
    write(OUT / "removed_structural_only.csv", [
        {"dataset_id": p["dataset_id"], "subject": p["subject"], "global_id": p["global_id"],
         "condition": p["condition"], "role": p["role"], "counted": p["counted"],
         "dataset_removed": p["dataset_id"] not in left} for p in removed])
    kept_ds = [dict(d, n_subjects_with_data=left[d["dataset_id"]], n_removed_structural_only=gone.get(d["dataset_id"], 0))
               for d in datasets if d["dataset_id"] in left]
    n_people = len({p["global_id"] for p in removed if p["counted"]})
    print(f"structural-only removed: {len(removed)} rows, {n_people} counted people, "
          f"{len(datasets) - len(kept_ds)} whole datasets")
    return keep, kept_ds


def link_cohorts_by_id(participants: list[dict]) -> None:
    """Datasets of the same cohort hold the same people. When their subject ids largely coincide
    (Jaccard >= 0.5), equal ids are the same person: merge their global ids (multimodal pairing)."""
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    by_cohort = defaultdict(lambda: defaultdict(dict))
    for p in participants:
        p["global_id"] = p["global_id"] or f"X:{p['dataset_id']}:{p['subject']}"
        if p["cohort"] and p["counted"]:
            by_cohort[p["cohort"]][p["dataset_id"]][canon(p["subject"])] = p["global_id"]
    linked = 0
    for dsets in by_cohort.values():
        names = sorted(dsets)
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = dsets[names[i]], dsets[names[j]]
                common = set(a) & set(b)
                if common and len(common) / len(set(a) | set(b)) >= 0.5:
                    for s in common:
                        ra, rb = find(a[s]), find(b[s])
                        if ra != rb:
                            parent[max(ra, rb)] = min(ra, rb)
                            linked += 1
    for p in participants:
        root = find(p["global_id"])
        p["global_id_source"] = "content_hash" if not p["global_id"].startswith("X:") else "dataset_local"
        if root != p["global_id"]:
            p["global_id"], p["global_id_source"] = root, "cohort_subject_id"
    print(f"cohort id links merged: {linked}")


def write(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def bounds(rows: list[dict]) -> tuple[int, int, int]:
    """Unique people with bounds. Rows of datasets in the same cohort are the same people (take the
    largest dataset); overlap groups may share people (lower bound takes the largest dataset)."""
    def grouped(key_fn):
        per_key = defaultdict(lambda: defaultdict(set))
        for p in rows:
            per_key[key_fn(p)][p.get("unit") or p["dataset_id"]].add(p["global_id"] or f"{p['dataset_id']}:{p['subject']}")
        people = set()
        for dsets in per_key.values():
            people |= max(dsets.values(), key=len)
        return people
    upper = grouped(lambda p: p["cohort"] or p["dataset_id"])
    lower = grouped(lambda p: p["overlap_group"] or p["cohort"] or p["dataset_id"])
    return len(lower), len(upper), len({p["dataset_id"] for p in rows})


def rank(participants: list[dict], datasets: list[dict]) -> list[dict]:
    counted = [p for p in participants if p["counted"]]
    by_cond = defaultdict(list)
    for p in counted:
        by_cond[p["condition"]].append(p)
    # modalities per global person across all their datasets
    person_mods = defaultdict(set)
    for p in counted:
        person_mods[p["global_id"] or f"{p['dataset_id']}:{p['subject']}"].update(filter(None, p["modalities"].split(";")))
    unresolved = defaultdict(int)
    for d in datasets:
        # published group sizes describe the whole release; skip them once part of it was removed
        if d["published_counts"] and not d["excluded_reason"] and not d.get("n_removed_structural_only"):
            for c, n in json.loads(d["published_counts"]).items():
                unresolved[c] = max(unresolved[c], n)  # cohort releases of the same people: take the largest
    out = []
    for cond, rows in by_cond.items():
        lo, hi, nds = bounds(rows)
        rec = {"condition": cond, "label": CONDITIONS.get(cond, cond), "people_min": lo, "people_max": hi,
               "datasets": nds, "plus_unresolved_published": unresolved.get(cond, 0)}
        for mod in ("MRI", "fMRI", "dMRI", "EEG", "MEG", "iEEG", "PET", "ASL", "fNIRS"):
            sub = [p for p in rows if mod in person_mods[p["global_id"] or f"{p['dataset_id']}:{p['subject']}"]]
            rec[f"{mod}_min"], rec[f"{mod}_max"] = bounds(sub)[:2] if sub else (0, 0)
        multi = [p for p in rows if len(person_mods[p["global_id"] or f"{p['dataset_id']}:{p['subject']}"] & {"EEG", "MEG", "iEEG", "fMRI", "PET", "dMRI"}) >= 2]
        rec["multimodal_2plus_max"] = bounds(multi)[1] if multi else 0
        out.append(rec)
    out.sort(key=lambda r: (r["condition"] in NON_PATIENT, -r["people_min"]))
    return out


if __name__ == "__main__":
    main()
