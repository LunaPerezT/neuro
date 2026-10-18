"""File-level version of the structural-only rule: drop anat recordings of people with no other technique,
and field maps of people with no fMRI/dMRI/ASL. Writes inventory/recordings_kept.csv + a summary."""
import csv
from collections import Counter, defaultdict
csv.field_size_limit(10**9)
OUT = "/home/claude/superdataset"
removed = {(r["dataset_id"], r["subject"]) for r in csv.DictReader(open(f"{OUT}/pheno/out/removed_structural_only.csv"))}
gid, mods = {}, defaultdict(set)
for p in csv.DictReader(open(f"{OUT}/pheno/out/participants.csv")):
    gid[(p["dataset_id"], p["subject"])] = p["global_id"]
    mods[p["global_id"]].update(filter(None, p["modalities"].split(";")))
FMAP_USERS = {"fMRI", "dMRI", "ASL"}
stats = Counter()
with open(f"{OUT}/inventory/recordings.csv") as fi, open(f"{OUT}/inventory/recordings_kept.csv", "w", newline="") as fo:
    r = csv.DictReader(fi)
    w = csv.DictWriter(fo, fieldnames=r.fieldnames)
    w.writeheader()
    for row in r:
        key = (row["dataset_id"], row["subject"])
        dt = row["datatype"]
        if key in removed or key not in gid:
            reason = "structural_only_person" if key in removed else "dataset_or_person_excluded"
        elif dt == "fmap" and not (mods[gid[key]] & FMAP_USERS):
            reason = "fmap_without_fmri_dmri_asl"
        else:
            reason = ""
        stats[(dt, reason or "kept")] += 1
        if not reason:
            w.writerow(row)
for (dt, why), n in sorted(stats.items()):
    print(f"{dt:6} {why:28} {n}")
print("kept", sum(n for (d, w), n in stats.items() if w == "kept"), "dropped", sum(n for (d, w), n in stats.items() if w != "kept"))
