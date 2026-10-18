"""Builds the subject list and per-subject file manifest for the ADHD-vs-controls HOI pilot.

Runs on the project machine (needs the superdataset outputs and git mirrors of the datasets).
Writes:
  data/subjects.csv  one row per person: dataset, subject, group, age, sex, comorbidity, source of preprocessed data
  data/files.csv     raw files to stage per subject (OpenNeuro path, size, role) or XCP-D files to fetch
  data/phenotype_<ds>.csv  all participants/phenotype columns for the selected subjects (wide)
"""
import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path("/home/claude/superdataset")
MIRRORS = Path("/tmp/claude-0/sz")          # blob:none clones of OpenNeuroDatasets/<ds>
DERIV = Path("/tmp/claude-0/deriv")         # blob:none clones of derivative datasets
OUT = Path(__file__).parent / "data"
DATASETS = ["ds000030", "ds005754", "ds007116", "ds007182", "ds008579"]
XCPD = {"ds008579": "ds008601"}             # datasets whose XCP-D parcellated series already exist on OpenNeuro
BRAINLIFE_MIRRORED = {"ds000030"}           # importable directly from brainlife.io/datasets
TARGET = "ADHD"
sys.path.insert(0, str(ROOT / "pheno"))


def git(ds_dir, *args):
    return subprocess.run(["git", "-C", str(ds_dir), *args], capture_output=True, text=True, timeout=300).stdout


def annex_size(ds_dir, path):
    """Size in bytes from the git-annex key the symlink points to (no data download)."""
    target = git(ds_dir, "cat-file", "-p", f"HEAD:{path}")
    m = re.search(r"-s(\d+)--", target)
    return int(m.group(1)) if m else len(target.encode())


def ses_of(path):
    m = re.search(r"ses-([A-Za-z0-9]+)", path)
    return m.group(1) if m else ""


def run_of(path):
    m = re.search(r"run-(\d+)", path)
    return int(m.group(1)) if m else 0


def pick_rest(paths, ds):
    rest = [p for p in paths if "/func/" in p and "task-rest_" in p and p.endswith("_bold.nii.gz")]
    if ds == "ds008579":
        rest = [p for p in rest if "acq-multiband" in p] or rest
    if not rest:
        return None, []
    rest.sort(key=lambda p: (ses_of(p), run_of(p), p))
    first = rest[0]
    if "echo-" in first:  # multi-echo: keep all echoes of that run
        stem = re.sub(r"_echo-\d+", "", first)
        echoes = sorted(p for p in rest if re.sub(r"_echo-\d+", "", p) == stem)
        return first, echoes
    return first, [first]


def pick_t1(paths, ses):
    t1 = [p for p in paths if "/anat/" in p and p.endswith("_T1w.nii.gz")]
    same = [p for p in t1 if ses_of(p) == ses] or t1
    same.sort(key=lambda p: ("acq-" in p, "rec-" in p, run_of(p), p))
    return same[0] if same else None


def entities(name):
    return set(re.findall(r"([a-zA-Z]+-[a-zA-Z0-9]+)", name.split(".")[0]))


def merged_sidecar(ds_dir, tree, path):
    """BIDS inheritance: top-level then subject/session-level sidecars whose entities are a subset of the file's."""
    fname = Path(path).name
    suffix = fname.split(".")[0].rsplit("_", 1)[-1]
    ents = entities(fname)
    meta = {}
    cands = sorted((p for p in tree if p.endswith(f"{suffix}.json") and "phenotype/" not in p),
                   key=lambda p: p.count("/"))
    for j in cands:
        if "/" in j and not path.startswith(j.rsplit("/", 1)[0] + "/") and j != path.replace(".nii.gz", ".json"):
            continue
        jname = Path(j).name
        if jname.split(".")[0].rsplit("_", 1)[-1] != suffix or not entities(jname) <= ents:
            continue
        try:
            meta.update(json.loads(git(ds_dir, "show", f"HEAD:{j}")))
        except json.JSONDecodeError:
            pass
    return meta


def pick_fmap(ds_dir, paths, bold, ses):
    """Fieldmap meant for the chosen BOLD run: IntendedFor, else B0FieldIdentifier naming the rest run."""
    cands = [p for p in paths if "/fmap/" in p and p.endswith(".json") and ses_of(p) == ses]
    rel = bold.split("/", 1)[1]  # path relative to subject dir
    run_tag = f"rest_run{run_of(bold):02d}"
    hits = []
    for j in cands:
        try:
            meta = json.loads(git(ds_dir, "show", f"HEAD:{j}"))
        except json.JSONDecodeError:
            continue
        intended = meta.get("IntendedFor") or []
        intended = [intended] if isinstance(intended, str) else intended
        b0 = meta.get("B0FieldIdentifier") or []
        b0 = [b0] if isinstance(b0, str) else b0
        if any(i.endswith(rel) or i.endswith(rel.split("/", 1)[-1]) for i in intended) or any(run_tag in x or x.endswith("rest") for x in b0):
            hits.append(j)
    files = []
    for j in hits:
        base = j[: -len(".json")]
        files += [p for p in paths if p.startswith(base) and p != j] + [j]
    return sorted(set(files))


def canon(x):
    x = re.sub(r"[^a-z0-9]", "", x.lower().removeprefix("sub-"))
    return re.sub(r"(?<![0-9])0+(?=[0-9])", "", x)


def table(ds):
    """participant -> {file:column: value} merged from participants.tsv and phenotype/*.tsv (as in the scope step)."""
    data = defaultdict(dict)
    for base in (ROOT / "meta/raw" / ds, ROOT / "meta/raw_extra" / ds):
        if not base.exists():
            continue
        for f in list(base.glob("participants.tsv")) + list(base.glob("phenotype/*.tsv")):
            try:
                df = pd.read_csv(f, sep="\t", dtype=str)
            except Exception:
                continue
            key = "participant_id" if "participant_id" in df else ("subject" if "subject" in df else None)
            if not key:
                continue
            for _, r in df.iterrows():
                k = canon(str(r[key]))
                for c, v in r.items():
                    if c != key:
                        data[k][f"{f.stem}:{c}"] = v
    return data


def main():
    P = pd.read_csv(ROOT / "pheno/out/participants.csv", dtype=str).fillna("")
    P = P[P.dataset_id.isin(DATASETS) & (P.counted == "True")]
    rec = pd.read_csv(ROOT / "inventory/recordings_kept.csv", dtype=str).fillna("")
    rec = rec[rec.dataset_id.isin(DATASETS)]
    subjects, files = [], []
    for ds in DATASETS:
        ds_dir = MIRRORS / ds
        tree = [p for p in git(ds_dir, "ls-tree", "-r", "--name-only", "HEAD").splitlines()]
        by_sub = defaultdict(list)
        for p in tree:
            if p.startswith("sub-"):
                by_sub[p.split("/")[0][4:]].append(p)
        top = [p for p in tree if "/" not in p and (p.endswith(".json") or p in ("participants.tsv",))]
        xcpd_tree = []
        if ds in XCPD:
            xcpd_tree = git(DERIV / XCPD[ds], "ls-tree", "-r", "--name-only", "HEAD").splitlines()
        for _, r in P[P.dataset_id == ds].iterrows():
            has_target = r.condition == TARGET or TARGET in r.other_conditions.split(";")
            if has_target:
                group = "ADHD"
            elif r.role in ("control", "healthy"):
                group = "control"
            elif r.role == "patient":
                group = "other_clinical"   # same study, other diagnosis: for specificity analyses later
            else:
                continue
            paths = by_sub.get(r.subject, [])
            bold, bolds = pick_rest(paths, ds)
            if not bold:
                continue
            ses = ses_of(bold)
            t1 = pick_t1(paths, ses)
            fmap = pick_fmap(ds_dir, paths, bold, ses) if ds in ("ds007116", "ds007182") else []
            if ds in XCPD:
                source = "xcpd_openneuro"
            elif ds in BRAINLIFE_MIRRORED:
                source = "brainlife_import"
            else:
                source = "brainlife_upload"
            bmeta = merged_sidecar(ds_dir, tree, bold)
            row = {
                "tr": bmeta.get("RepetitionTime", ""),
                "echo_times": ";".join(str(merged_sidecar(ds_dir, tree, b).get("EchoTime", "")) for b in bolds) if len(bolds) > 1 else "",
                "dataset_id": ds, "subject": r.subject, "global_id": r.global_id, "group": group,
                "primary_condition": r.condition, "other_conditions": r.other_conditions,
                "age": r.age, "sex": r.sex, "session": ses, "rest_run": run_of(bold),
                "n_echoes": len(bolds), "has_fmap": bool(fmap), "source": source,
                "priority": 1 if group in ("ADHD", "control") else 2,
            }
            if source == "xcpd_openneuro":
                stem = Path(bold).name.split("_bold")[0]
                # XCP-D keeps entity order sub_ses_task_acq[_run]; match on subject+session+task-rest+multiband
                pre = f"sub-{r.subject}/ses-{ses}/func/" if ses else f"sub-{r.subject}/func/"
                want = [p for p in xcpd_tree if p.startswith(pre) and "task-rest" in p and "acq-multiband" in p and (
                    p.endswith("_motion.tsv") or p.endswith("_desc-linc_qc.tsv")
                    or re.search(r"_seg-(4S456Parcels|Tian)_stat-mean_timeseries\.tsv$", p))]
                if not any("4S456Parcels" in p for p in want):
                    continue
                row["n_xcpd_runs"] = len({re.sub(r"_(motion|space|seg).*", "", p) for p in want})
                for p in want:
                    files.append({"dataset_id": ds, "subject": r.subject, "repo": XCPD[ds], "path": p,
                                  "role": "xcpd", "bytes": annex_size(DERIV / XCPD[ds], p)})
            else:
                for role, plist in (("t1w", [t1] if t1 else []), ("bold", bolds), ("fmap", fmap)):
                    for p in plist:
                        files.append({"dataset_id": ds, "subject": r.subject, "repo": ds, "path": p, "role": role,
                                      "bytes": annex_size(ds_dir, p)})
                        side = p.replace(".nii.gz", ".json")
                        if role != "fmap" and side in paths:
                            files.append({"dataset_id": ds, "subject": r.subject, "repo": ds, "path": side,
                                          "role": role + "_json", "bytes": 0})
            subjects.append(row)
        for p in top:
            files.append({"dataset_id": ds, "subject": "", "repo": ds, "path": p, "role": "top_level", "bytes": 0})
        # phenotype (wide) for the selected people
        tab = table(ds)
        sel = {canon(s["subject"]): s["subject"] for s in subjects if s["dataset_id"] == ds}
        rows = [{"subject": sel[k], **v} for k, v in tab.items() if k in sel]
        if rows:
            pd.DataFrame(rows).to_csv(OUT / f"phenotype_{ds}.csv", index=False)
    S = pd.DataFrame(subjects)
    S["has_t1w"] = S.apply(lambda r: r.source == "xcpd_openneuro" or any(
        f["role"] == "t1w" and f["dataset_id"] == r.dataset_id and f["subject"] == r.subject for f in files), axis=1)
    S.loc[~S.has_t1w, "priority"] = 0          # cannot be preprocessed
    # label used on brainlife: original ID for the dataset imported there, global person ID for uploads
    S["brainlife_subject"] = S.apply(lambda r: r.subject if r.source == "brainlife_import" else r.global_id, axis=1)
    assert not S[S.source == "brainlife_upload"].brainlife_subject.duplicated().any()
    F = pd.DataFrame(files)
    S.to_csv(OUT / "subjects.csv", index=False)
    F.to_csv(OUT / "files.csv", index=False)
    gb = F.groupby(["dataset_id", "subject"]).bytes.sum() / 1e9
    S = S.merge(gb.rename("gb").reset_index(), on=["dataset_id", "subject"], how="left")
    print(S.groupby(["dataset_id", "source", "group"]).agg(n=("subject", "size"), gb=("gb", "sum"), max_gb=("gb", "max")).round(2))
    print("priority-1 people:", (S.priority == 1).sum(), "| GB to stage (priority 1):", round(S[S.priority == 1].gb.sum(), 1))


if __name__ == "__main__":
    main()
