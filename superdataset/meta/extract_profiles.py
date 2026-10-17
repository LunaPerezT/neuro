"""Build one compact 'label profile' per dataset and triage datasets for annotation.

A profile holds everything needed to decide how each participant should be labelled:
candidate group columns with their distinct values and data-dictionary levels, group codes
in subject ids, OpenNeuro's dxStatus/studyDomain, and disease keywords found in the README.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "/home/claude/openneuro-mcp/src")
from openneuro_mcp.bids import NA_VALUES, id_prefix_groups, parse_sidecar, parse_tsv  # noqa: E402

RAW = Path("raw")
GROUP_HINTS = ("group", "diagnos", "dx", "condition", "status", "patient", "control", "cohort", "disease",
               "clinical", "population", "category", "class", "health", "pathology", "disorder", "type", "arm",
               "drug", "treatment", "medication", "label", "subject_type", "participant_type", "sample")
NOT_GROUP = ("duration", "onset", "age", "date", "time", "score", "dose", "severity", "years", "handed",
             "hand", "sex", "gender", "weight", "height", "bmi", "education", "session", "id", "site", "_ms",
             "hz", "count", "number", "rate", "total", "sum")
DISEASE_TERMS = [
    "parkinson", "alzheimer", "dementia", "mild cognitive impairment", "mci", "epilep", "seizure", "schizophren",
    "psychosis", "psychotic", "bipolar", "depress", "mdd", "anxiety", "ptsd", "adhd", "autis", "asd",
    "stroke", "aphasia", "traumatic brain injury", "tbi", "concussion", "multiple sclerosis", "als",
    "amyotrophic", "huntington", "migraine", "tinnitus", "chronic pain", "pain patients", "insomnia",
    "sleep apnea", "narcolepsy", "coma", "disorders of consciousness", "vegetative", "unresponsive",
    "covid", "sars-cov-2", "alcohol", "substance", "cocaine", "cannabis", "opioid", "smok", "nicotine",
    "dyslexia", "obsessive", "ocd", "tourette", "essential tremor", "dystonia", "cerebral palsy",
    "down syndrome", "fragile x", "rett", "batten", "cln3", "neuralgia", "glioma", "tumor", "tumour",
    "anesthe", "anaesthe", "propofol", "ketamine", "psilocybin", "lsd", "patients", "clinical population",
    "deaf", "blind", "hearing loss", "cochlear implant", "amputee", "spinal cord injury", "neuropathy",
    "eating disorder", "anorexia", "bulimia", "preterm", "premature", "neonat", "delirium", "encephalopathy",
]


def is_group_column(name: str) -> bool:
    n = name.lower()
    if n in ("participant_id",):
        return False
    if any(h in n for h in GROUP_HINTS) and not any(x in n for x in NOT_GROUP):
        return True
    return False


def read(ds: str, name: str) -> str | None:
    p = RAW / ds / name
    return p.read_text(errors="replace") if p.exists() else None


def readme(ds: str) -> str:
    for n in ("README", "README.md", "README.txt"):
        t = read(ds, n)
        if t:
            return t
    return ""


def disease_hits(text: str) -> list[str]:
    t = text.lower()
    hits = []
    for term in DISEASE_TERMS:
        pattern = r"\b" + re.escape(term) if len(term) <= 4 else re.escape(term)
        if re.search(pattern + (r"\b" if len(term) <= 4 else ""), t):
            hits.append(term)
    return hits


def profile(row: dict) -> dict:
    ds = row["id"]
    tsv = read(ds, "participants.tsv")
    sidecar = parse_sidecar(read(ds, "participants.json"))
    desc = parse_sidecar(read(ds, "dataset_description.json"))
    rm = readme(ds)
    prof = {
        "id": ds, "name": row["name"] or desc.get("Name"), "n_subjects_census": row["n_subjects"],
        "dx_status": row.get("dx_status"), "study_domain": row.get("study_domain"),
        "species": row.get("species"), "tasks": row.get("tasks")[:8], "paper_doi": row.get("paper_doi"),
        "has_participants_tsv": tsv is not None, "n_rows": 0, "columns": [], "group_columns": {},
        "id_prefix_groups": None, "readme_disease_terms": [], "readme_head": "",
    }
    if tsv:
        cols, rows = parse_tsv(tsv)
        prof["n_rows"] = len(rows)
        prof["columns"] = cols
        for c in cols:
            vals = [r.get(c, "") for r in rows]
            present = [v for v in vals if v.strip().lower() not in NA_VALUES]
            distinct = Counter(present)
            meta = sidecar.get(c) if isinstance(sidecar.get(c), dict) else {}
            levels = meta.get("Levels") if isinstance(meta.get("Levels"), dict) else None
            if (is_group_column(c) or levels and any(disease_hits(str(v)) or "control" in str(v).lower() for v in levels.values())) \
                    and 1 < len(distinct) <= 25 or (is_group_column(c) and len(distinct) == 1):
                prof["group_columns"][c] = {
                    "values": dict(distinct.most_common()),
                    "missing": len(vals) - len(present),
                    "levels": levels,
                    "description": (meta.get("Description") or "")[:200],
                }
        prof["id_prefix_groups"] = id_prefix_groups([r.get("participant_id", "") for r in rows])
    text_for_terms = " ".join(filter(None, [prof["name"] or "", rm[:6000], row.get("dx_status") or "", row.get("study_domain") or ""]))
    prof["readme_disease_terms"] = disease_hits(text_for_terms)
    prof["readme_head"] = re.sub(r"\s+", " ", rm)[:700]
    return prof


def triage(p: dict) -> str:
    dx = (p["dx_status"] or "").lower()
    has_groups = bool(p["group_columns"]) or bool(p["id_prefix_groups"])
    if has_groups or p["readme_disease_terms"]:
        return "review"
    if dx in ("healthy / control", "healthy", "control"):
        return "auto_healthy"
    if not p["has_participants_tsv"]:
        return "review"
    return "auto_presumed_healthy"


def main() -> None:
    census = json.load(open("census_human.json"))
    profiles = [profile(r) for r in census]
    for p in profiles:
        p["triage"] = triage(p)
    with open("profiles.jsonl", "w") as f:
        for p in profiles:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    t = Counter(p["triage"] for p in profiles)
    subj = Counter()
    for p in profiles:
        subj[p["triage"]] += p["n_subjects_census"]
    print("triage:", {k: (v, subj[k]) for k, v in t.items()})
    print("with group columns:", sum(1 for p in profiles if p["group_columns"]),
          "| with id prefix groups:", sum(1 for p in profiles if p["id_prefix_groups"]))
    cols = Counter(c for p in profiles for c in p["group_columns"])
    print("most common group column names:", cols.most_common(30))


if __name__ == "__main__":
    main()
