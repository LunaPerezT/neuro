"""Deduplicate datasets and link the same people across datasets using git-annex content hashes.

Two (dataset, subject) records are the same person when they share at least MIN_SHARED identical
data files (same annex key => same SHA-256). Union-find over those links gives global person IDs.
Datasets are duplicates/subsets when most of their annexed data files exist in another dataset.

Outputs (linked/):
  people.csv          global_id, dataset_id, subject, datatypes for every (dataset, subject)
  person_summary.csv  one row per global person: n_datasets, datasets, all datatypes, multimodal flag
  dataset_overlap.csv pairs of datasets sharing files, with shared counts and relation
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10**9)
INV, OUT = Path(__file__).resolve().parent / "inventory", Path(__file__).resolve().parent / "linked"
MIN_SHARED = 2          # files a subject must share to be linked to another dataset's subject
SUBSET_RATIO = 0.9      # share of the smaller dataset's files found in the larger one
MODALITY = {"anat": "MRI", "func": "fMRI", "dwi": "dMRI", "fmap": "MRI", "perf": "ASL", "eeg": "EEG", "meg": "MEG",
            "ieeg": "iEEG", "pet": "PET", "nirs": "fNIRS", "beh": "behaviour", "motion": "motion", "emg": "EMG", "micr": "microscopy"}


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    oid_owners = defaultdict(set)            # oid -> {(ds, sub)}
    subj_files = defaultdict(set)            # (ds, sub) -> {oid}
    subj_types = defaultdict(set)            # (ds, sub) -> {datatype}
    ds_files = defaultdict(set)
    for r in csv.DictReader(open(INV / "recordings.csv")):
        key = (r["dataset_id"], r["subject"])
        subj_types[key].add(r["datatype"])
        if r["annexed"] == "True" and r["oid"]:
            oid_owners[r["oid"]].add(key)
            subj_files[key].add(r["oid"])
            ds_files[r["dataset_id"]].add(r["oid"])

    # dataset-level overlap
    pair_shared = Counter()
    for owners in oid_owners.values():
        dss = sorted({d for d, _ in owners})
        for i in range(len(dss)):
            for j in range(i + 1, len(dss)):
                pair_shared[(dss[i], dss[j])] += 1
    overlaps = []
    for (a, b), n in pair_shared.items():
        if n < 3:
            continue
        na, nb = len(ds_files[a]), len(ds_files[b])
        small, big = (a, b) if na <= nb else (b, a)
        ratio = n / min(na, nb)
        relation = ("identical" if ratio >= SUBSET_RATIO and abs(na - nb) <= 0.1 * max(na, nb) else
                    f"{small} subset of {big}" if ratio >= SUBSET_RATIO else "partial overlap")
        overlaps.append({"dataset_a": a, "dataset_b": b, "files_a": na, "files_b": nb, "shared": n,
                         "share_of_smaller": round(ratio, 3), "relation": relation})
    overlaps.sort(key=lambda r: -r["shared"])

    # person-level linking
    uf = UnionFind()
    for key in subj_types:
        uf.find(key)
    shared_by_pair = Counter()
    for owners in oid_owners.values():
        if 1 < len(owners) <= 20:  # ignore files duplicated across very many subjects (templates, placeholders)
            owners = sorted(owners)
            for i in range(len(owners)):
                for j in range(i + 1, len(owners)):
                    if owners[i][0] != owners[j][0]:
                        shared_by_pair[(owners[i], owners[j])] += 1
    for (a, b), n in shared_by_pair.items():
        if n >= MIN_SHARED:
            uf.union(a, b)

    roots = sorted({uf.find(k) for k in subj_types})
    gid = {root: f"NB{i + 1:07d}" for i, root in enumerate(roots)}
    members = defaultdict(list)
    with open(OUT / "people.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["global_id", "dataset_id", "subject", "datatypes"])
        for key in sorted(subj_types):
            g = gid[uf.find(key)]
            members[g].append(key)
            w.writerow([g, key[0], key[1], ";".join(sorted(subj_types[key]))])
    multi_counter = Counter()
    with open(OUT / "person_summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["global_id", "n_datasets", "datasets", "datatypes", "modalities", "n_modalities"])
        for g, keys in members.items():
            types = set().union(*(subj_types[k] for k in keys))
            mods = sorted({MODALITY.get(t, t) for t in types} - {"behaviour"})
            multi_counter[len(mods)] += 1
            w.writerow([g, len({k[0] for k in keys}), ";".join(sorted({k[0] for k in keys})), ";".join(sorted(types)),
                        ";".join(mods), len(mods)])
    with open(OUT / "dataset_overlap.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(overlaps[0].keys()) if overlaps else ["dataset_a"])
        w.writeheader()
        w.writerows(overlaps)

    cross = sum(1 for keys in members.values() if len({k[0] for k in keys}) > 1)
    print(f"(dataset, subject) records: {len(subj_types)} | unique people: {len(members)} | "
          f"people found in >1 dataset: {cross}")
    print("people by number of modalities:", dict(sorted(multi_counter.items())))
    print("dataset pairs sharing files:", len(overlaps), Counter(r["relation"].split(" ")[-1] if "subset" in r["relation"] else r["relation"] for r in overlaps))


if __name__ == "__main__":
    main()
