"""Pre-computes the fully inherited BIDS sidecar of every file to be uploaded (data/sidecars.jsonl.gz),
so the PC does not need to resolve BIDS inheritance."""
import gzip, json
import pandas as pd
from select_subjects import MIRRORS, git, merged_sidecar

F = pd.read_csv("data/files.csv", dtype=str).fillna("")
S = pd.read_csv("data/subjects.csv", dtype=str).fillna("")
up = set(S[S.source == "brainlife_upload"].dataset_id)
F = F[F.dataset_id.isin(up) & F.role.isin(["t1w", "bold", "fmap"]) & F.path.str.endswith(".nii.gz")]
n = 0
with gzip.open("data/sidecars.jsonl.gz", "wt") as out:
    for ds, grp in F.groupby("dataset_id"):
        tree = git(MIRRORS / ds, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
        for p in grp.path:
            out.write(json.dumps({"dataset_id": ds, "path": p, "meta": merged_sidecar(MIRRORS / ds, tree, p)}) + "\n")
            n += 1
print(n, "sidecars")
