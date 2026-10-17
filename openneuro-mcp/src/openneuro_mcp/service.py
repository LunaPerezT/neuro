"""Business logic behind each MCP tool. Functions return plain dicts (JSON-ready)."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from graphql import GraphQLSyntaxError, OperationType, parse
from graphql.language import OperationDefinitionNode

from . import queries as Q
from .bids import id_prefix_groups, likely_group_columns, parse_sidecar, parse_tsv, summarize_column
from .client import (
    S3_HTTP_BASE,
    BackendUnavailable,
    OpenNeuroClient,
    OpenNeuroError,
    normalize_dataset_id,
    safe_relative_path,
)

DATASET_URL = "https://openneuro.org/datasets/{id}"
CENSUS_TTL = 6 * 3600
CENSUS_PAGE_SIZE = 100
CENSUS_GROUPS_PAGE_SIZE = 25  # per-subject metadata makes pages heavier


# ---------------------------------------------------------------- shared helpers
def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _summary_row(node: dict[str, Any]) -> dict[str, Any]:
    """Flatten a Dataset node (with latestSnapshot.summary and metadata) into one row."""
    snap = node.get("latestSnapshot") or {}
    summary = snap.get("summary") or {}
    meta = node.get("metadata") or {}
    ages = [a for a in (meta.get("ages") or []) if isinstance(a, (int, float))]
    return {
        "id": node.get("id"),
        "name": node.get("name"),
        "url": DATASET_URL.format(id=node.get("id")),
        "latest_tag": snap.get("tag"),
        "modalities": summary.get("modalities") or [],
        "primary_modality": summary.get("primaryModality"),
        "n_subjects": len(summary.get("subjects") or []),
        "n_sessions": len(summary.get("sessions") or []),
        "tasks": summary.get("tasks") or [],
        "size_bytes": _int(summary.get("size")),
        "data_processed": summary.get("dataProcessed"),
        "dx_status": meta.get("dxStatus"),
        "species": meta.get("species"),
        "study_domain": meta.get("studyDomain"),
        "age_min": min(ages) if ages else None,
        "age_max": max(ages) if ages else None,
        "paper_doi": meta.get("associatedPaperDOI"),
        "synthetic": meta.get("syntheticDataset"),
        "created": node.get("created"),
    }


async def _latest_tag(client: OpenNeuroClient, dataset_id: str) -> str:
    data = await client.graphql(Q.LATEST_TAG, {"id": dataset_id})
    ds = data.get("dataset")
    if not ds:
        raise OpenNeuroError(f"Dataset {dataset_id} was not found on OpenNeuro (or it is private).")
    return ds["latestSnapshot"]["tag"]


async def _list_dir(client: OpenNeuroClient, dataset_id: str, tag: str, path: str) -> list[dict[str, Any]]:
    """List one directory of a snapshot by walking from the root (the API addresses dirs by id)."""
    tree: str | None = None
    walked: list[str] = []
    for segment in [p for p in path.split("/") if p]:
        entries = await _files(client, dataset_id, tag, tree)
        match = next((e for e in entries if e["filename"] == segment), None)
        if match is None:
            where = "/".join(walked) or "the dataset root"
            raise OpenNeuroError(
                f"'{segment}' does not exist in {where} of {dataset_id}@{tag}. "
                "Call openneuro_list_files on the parent folder to see valid names."
            )
        if not match.get("directory"):
            raise OpenNeuroError(f"'{'/'.join(walked + [segment])}' is a file, not a folder. Use openneuro_read_file.")
        tree = match["id"]
        walked.append(segment)
    return await _files(client, dataset_id, tag, tree)


async def _files(client: OpenNeuroClient, dataset_id: str, tag: str, tree: str | None) -> list[dict[str, Any]]:
    data = await client.graphql(Q.LIST_FILES, {"id": dataset_id, "tag": tag, "tree": tree})
    snap = data.get("snapshot")
    if snap is None:
        raise OpenNeuroError(f"Snapshot {dataset_id}@{tag} was not found. Check the tag with openneuro_get_dataset.")
    return [f for f in (snap.get("files") or []) if f]


async def _read_text(
    client: OpenNeuroClient, dataset_id: str, path: str, tag: str | None, max_bytes: int
) -> dict[str, Any]:
    """Read a text file, preferring OpenNeuro and falling back to the GitHub mirror."""
    path = safe_relative_path(path)
    if not path:
        raise OpenNeuroError("Give a file path such as 'participants.tsv' or 'sub-01/eeg/sub-01_task-rest_eeg.json'.")
    try:
        tag = tag or await _latest_tag(client, dataset_id)
        parent, _, name = path.rpartition("/")
        entries = await _list_dir(client, dataset_id, tag, parent)
        entry = next((e for e in entries if e["filename"] == name), None)
        if entry is None:
            return {"found": False, "path": path, "tag": tag, "source": "graphql"}
        if entry.get("directory"):
            raise OpenNeuroError(f"'{path}' is a folder. Use openneuro_list_files to list it.")
        url = (entry.get("urls") or [f"{S3_HTTP_BASE}/{dataset_id}/{path}"])[0]
        text, truncated = await client.fetch_text(url, max_bytes)
        return {"found": True, "path": path, "tag": tag, "source": "graphql", "url": url,
                "size_bytes": _int(entry.get("size")), "truncated": truncated, "text": text}
    except BackendUnavailable:
        if not client.github_enabled:
            raise
    text = await client.github_text(dataset_id, path)
    if text is None:
        return {"found": False, "path": path, "tag": "latest (GitHub mirror)", "source": "github-mirror"}
    truncated = len(text.encode()) > max_bytes
    return {"found": True, "path": path, "tag": "latest (GitHub mirror)", "source": "github-mirror",
            "truncated": truncated, "text": text.encode()[:max_bytes].decode("utf-8", "replace")}


# ---------------------------------------------------------------- tools
async def search_datasets(
    client: OpenNeuroClient,
    *,
    keywords: list[str] | None,
    modality: str | None,
    diagnosis: str | None,
    tasks: list[str] | None,
    species: str | None,
    age_min: int | None,
    age_max: int | None,
    subjects_min: int | None,
    subjects_max: int | None,
    sort: str,
    limit: int,
    cursor: str | None,
) -> dict[str, Any]:
    query: dict[str, Any] = {"sortBy": sort}
    if keywords:
        query["keywords"] = keywords
    if modality:
        query["modality"] = modality.strip().lower()  # the API indexes modalities in lowercase
    if diagnosis:
        query["diagnosis"] = diagnosis
    if tasks:
        query["tasks"] = tasks
    if species:
        query["species"] = species
    if age_min is not None or age_max is not None:
        query["ageRange"] = [age_min if age_min is not None else 0, age_max if age_max is not None else 150]
    if subjects_min is not None or subjects_max is not None:
        query["subjectCountRange"] = [subjects_min or 0, subjects_max if subjects_max is not None else 1_000_000]
    try:
        data = await client.graphql(Q.SEARCH_DATASETS, {"query": query, "first": limit, "after": cursor})
    except BackendUnavailable as exc:
        raise OpenNeuroError(
            f"{exc} Search needs the OpenNeuro API; the GitHub mirror cannot be searched. "
            "Run this server on a machine with access to openneuro.org."
        ) from exc
    conn = data.get("advancedSearch") or {}
    page = conn.get("pageInfo") or {}
    rows = [_summary_row(e["node"]) for e in (conn.get("edges") or []) if e and e.get("node")]
    return {
        "query": query,
        "total": page.get("count"),
        "count": len(rows),
        "has_more": bool(page.get("hasNextPage")),
        "next_cursor": page.get("endCursor") if page.get("hasNextPage") else None,
        "datasets": rows,
    }


async def get_dataset(
    client: OpenNeuroClient, dataset_id: str, *, tag: str | None, include_readme: bool, readme_chars: int
) -> dict[str, Any]:
    dataset_id = normalize_dataset_id(dataset_id)
    try:
        if tag:
            base = await client.graphql(Q.GET_DATASET, {"id": dataset_id})
            snap_data = await client.graphql(Q.GET_SNAPSHOT, {"id": dataset_id, "tag": tag})
            ds = base.get("dataset")
            snap = snap_data.get("snapshot")
            if snap is None:
                raise OpenNeuroError(f"{dataset_id} has no snapshot '{tag}'. Omit tag to use the latest version.")
        else:
            data = await client.graphql(Q.GET_DATASET, {"id": dataset_id})
            ds = data.get("dataset")
            snap = (ds or {}).get("latestSnapshot")
        if not ds:
            raise OpenNeuroError(f"Dataset {dataset_id} was not found on OpenNeuro (or it is private).")
        return _dataset_from_graphql(ds, snap or {}, include_readme, readme_chars)
    except BackendUnavailable:
        if not client.github_enabled:
            raise
    return await _dataset_from_github(client, dataset_id, include_readme, readme_chars)


def _dataset_from_graphql(ds: dict, snap: dict, include_readme: bool, readme_chars: int) -> dict[str, Any]:
    summary = snap.get("summary") or {}
    subject_meta = [s for s in (summary.get("subjectMetadata") or []) if s]
    groups = Counter((s.get("group") or "").strip() for s in subject_meta if (s.get("group") or "").strip())
    sexes = Counter((s.get("sex") or "").strip() for s in subject_meta if (s.get("sex") or "").strip())
    ages = [s["age"] for s in subject_meta if isinstance(s.get("age"), (int, float))]
    desc = snap.get("description") or {}
    readme = snap.get("readme") or ""
    out: dict[str, Any] = {
        "source": "graphql",
        "id": ds.get("id"),
        "name": ds.get("name") or desc.get("Name"),
        "url": DATASET_URL.format(id=ds.get("id")),
        "created": ds.get("created"),
        "published": ds.get("publishDate"),
        "tag": snap.get("tag"),
        "versions": [s.get("tag") for s in (ds.get("snapshots") or []) if s],
        "size_bytes": _int(snap.get("size") or summary.get("size")),
        "modalities": summary.get("modalities") or [],
        "primary_modality": summary.get("primaryModality"),
        "n_subjects": len(summary.get("subjects") or []),
        "n_sessions": len(summary.get("sessions") or []),
        "tasks": summary.get("tasks") or [],
        "total_files": summary.get("totalFiles"),
        "data_processed": summary.get("dataProcessed"),
        "groups_from_validator": dict(groups.most_common()),
        "sex_counts": dict(sexes.most_common()),
        "age_range": [min(ages), max(ages)] if ages else None,
        "metadata": ds.get("metadata") or {},
        "description": desc,
        "related": [r for r in (snap.get("related") or []) if r],
        "derivatives": [d for d in (ds.get("derivatives") or []) if d],
    }
    if include_readme:
        out["readme"] = readme[:readme_chars]
        out["readme_truncated"] = len(readme) > readme_chars
    return out


async def _dataset_from_github(
    client: OpenNeuroClient, dataset_id: str, include_readme: bool, readme_chars: int
) -> dict[str, Any]:
    desc_text = await client.github_text(dataset_id, "dataset_description.json")
    if desc_text is None:
        raise OpenNeuroError(
            f"{dataset_id} was not found on the OpenNeuroDatasets GitHub mirror and openneuro.org is unreachable."
        )
    desc = parse_sidecar(desc_text)
    out: dict[str, Any] = {
        "source": "github-mirror",
        "note": "openneuro.org was unreachable; showing git-tracked metadata from the GitHub mirror "
                "(latest version only, no file sizes or validator summary).",
        "id": dataset_id,
        "name": desc.get("Name"),
        "url": DATASET_URL.format(id=dataset_id),
        "description": desc,
    }
    participants = await client.github_text(dataset_id, "participants.tsv")
    if participants:
        _, rows = parse_tsv(participants)
        out["n_subjects"] = len(rows)
    changes = await client.github_text(dataset_id, "CHANGES")
    if changes:
        first = next((line.strip() for line in changes.splitlines() if line.strip()), "")
        out["latest_version_line"] = first
    if include_readme:
        readme = (await client.github_text(dataset_id, "README")) or (
            await client.github_text(dataset_id, "README.md")) or ""
        out["readme"] = readme[:readme_chars]
        out["readme_truncated"] = len(readme) > readme_chars
    return out


async def get_participants(
    client: OpenNeuroClient, dataset_id: str, *, tag: str | None, max_rows: int, offset: int
) -> dict[str, Any]:
    dataset_id = normalize_dataset_id(dataset_id)
    tsv = await _read_text(client, dataset_id, "participants.tsv", tag, 5_000_000)
    if not tsv["found"]:
        return {
            "id": dataset_id,
            "found": False,
            "message": "This dataset has no participants.tsv. Subject info may be in the README or "
                       "phenotype/ folder; try openneuro_get_dataset (groups_from_validator) or "
                       "openneuro_list_files with path='phenotype'.",
        }
    sidecar_file = await _read_text(client, dataset_id, "participants.json", tsv["tag"] if tsv["source"] == "graphql" else None, 500_000)
    sidecar = parse_sidecar(sidecar_file.get("text")) if sidecar_file.get("found") else {}
    columns, rows = parse_tsv(tsv["text"])
    ids = [r.get("participant_id", "") for r in rows]
    return {
        "id": dataset_id,
        "found": True,
        "source": tsv["source"],
        "tag": tsv["tag"],
        "truncated_file": tsv.get("truncated", False),
        "n_participants": len(rows),
        "has_data_dictionary": bool(sidecar),
        "likely_group_columns": likely_group_columns(columns),
        "id_prefix_groups": id_prefix_groups(ids),
        "columns": [summarize_column(c, [r.get(c, "") for r in rows], sidecar) for c in columns],
        "rows_offset": offset,
        "rows": rows[offset: offset + max_rows],
        "has_more_rows": offset + max_rows < len(rows),
    }


async def list_files(
    client: OpenNeuroClient, dataset_id: str, *, path: str, tag: str | None, limit: int, offset: int
) -> dict[str, Any]:
    dataset_id = normalize_dataset_id(dataset_id)
    path = safe_relative_path(path)
    try:
        tag = tag or await _latest_tag(client, dataset_id)
    except BackendUnavailable as exc:
        raise OpenNeuroError(
            f"{exc} Listing folders needs the OpenNeuro API. With only the GitHub mirror you can still "
            "read known text files with openneuro_read_file."
        ) from exc
    entries = await _list_dir(client, dataset_id, tag, path)
    entries.sort(key=lambda e: (not e.get("directory"), e["filename"]))
    files = [e for e in entries if not e.get("directory")]
    page = entries[offset: offset + limit]
    return {
        "id": dataset_id,
        "tag": tag,
        "path": path or "/",
        "n_entries": len(entries),
        "n_folders": len(entries) - len(files),
        "n_files": len(files),
        "files_size_bytes": sum(_int(e.get("size")) or 0 for e in files),
        "offset": offset,
        "has_more": offset + limit < len(entries),
        "entries": [
            {
                "name": e["filename"],
                "path": f"{path}/{e['filename']}" if path else e["filename"],
                "type": "folder" if e.get("directory") else "file",
                "size_bytes": _int(e.get("size")),
                "annexed": e.get("annexed"),
                "url": (e.get("urls") or [None])[0],
            }
            for e in page
        ],
    }


async def read_file(
    client: OpenNeuroClient, dataset_id: str, *, path: str, tag: str | None, max_chars: int
) -> dict[str, Any]:
    dataset_id = normalize_dataset_id(dataset_id)
    result = await _read_text(client, dataset_id, path, tag, max_chars * 4)
    if not result["found"]:
        raise OpenNeuroError(
            f"'{result['path']}' was not found in {dataset_id} ({result['tag']}). "
            "Use openneuro_list_files to browse the dataset."
        )
    text = result["text"]
    result["truncated"] = result.get("truncated", False) or len(text) > max_chars
    result["text"] = text[:max_chars]
    result["id"] = dataset_id
    return result


async def get_download_info(client: OpenNeuroClient, dataset_id: str, *, include: str | None) -> dict[str, Any]:
    dataset_id = normalize_dataset_id(dataset_id)
    out: dict[str, Any] = {"id": dataset_id, "url": DATASET_URL.format(id=dataset_id)}
    try:
        data = await client.graphql(Q.DOWNLOAD_INFO, {"id": dataset_id})
        ds = data.get("dataset")
        if not ds:
            raise OpenNeuroError(f"Dataset {dataset_id} was not found on OpenNeuro.")
        snap = ds.get("latestSnapshot") or {}
        summary = snap.get("summary") or {}
        out.update(
            name=ds.get("name"),
            tag=snap.get("tag"),
            size_bytes=_int(snap.get("size") or summary.get("size")),
            total_files=summary.get("totalFiles"),
            n_subjects=len(summary.get("subjects") or []),
            modalities=summary.get("modalities") or [],
            derivatives=[d for d in (ds.get("derivatives") or []) if d],
        )
    except BackendUnavailable:
        out["note"] = "openneuro.org was unreachable; sizes are unknown but the commands below are valid."
    tag = out.get("tag")
    include_flag = f" --include '{include}'" if include else ""
    s3_include = f" --exclude '*' --include '{include}'" if include else ""
    out["commands"] = {
        "openneuro-py": f"openneuro-py download --dataset {dataset_id}"
                        + (f" --tag {tag}" if tag else "") + include_flag,
        "datalad": f"datalad install https://github.com/OpenNeuroDatasets/{dataset_id}.git && "
                   f"cd {dataset_id} && datalad get {include or '.'}",
        "aws_s3": f"aws s3 sync --no-sign-request s3://openneuro.org/{dataset_id} {dataset_id}/{s3_include}",
    }
    out["advice"] = (
        "Check size_bytes before downloading. Download only what the analysis needs with --include "
        "(e.g. 'sub-*/eeg/*rest*'), and prefer an existing derivative (e.g. fMRIPrep output) when listed."
    )
    return out


async def census(
    client: OpenNeuroClient,
    *,
    modality: str | None,
    include_groups: bool,
    refresh: bool,
    max_datasets: int,
) -> list[dict[str, Any]]:
    """Fetch (and cache) one row per public dataset, optionally with per-subject group counts."""
    modality = modality.strip().lower() if modality else None  # the API expects lowercase
    key = f"census:{modality or 'all'}:{include_groups}:{max_datasets}"
    if not refresh and (cached := client.cache_get(key)) is not None:
        return cached
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    try:
        while len(rows) < max_datasets:
            data = await client.graphql(
                Q.CENSUS_PAGE,
                {"first": min(CENSUS_GROUPS_PAGE_SIZE if include_groups else CENSUS_PAGE_SIZE, max_datasets - len(rows)),
                 "after": cursor,
                 "modality": modality, "withGroups": include_groups},
            )
            conn = data.get("datasets") or {}
            for edge in conn.get("edges") or []:
                node = (edge or {}).get("node")
                if not node:
                    continue
                row = _summary_row(node)
                if include_groups:
                    meta = ((node.get("latestSnapshot") or {}).get("summary") or {}).get("subjectMetadata") or []
                    groups = Counter((m.get("group") or "").strip().lower() for m in meta if m and (m.get("group") or "").strip())
                    row["group_counts"] = dict(groups.most_common())
                rows.append(row)
            page = conn.get("pageInfo") or {}
            if not page.get("hasNextPage") or not page.get("endCursor"):
                break
            cursor = page["endCursor"]
    except BackendUnavailable as exc:
        raise OpenNeuroError(f"{exc} The census needs the OpenNeuro API.") from exc
    client.cache_set(key, rows, CENSUS_TTL)
    return rows


def filter_and_aggregate(
    rows: list[dict[str, Any]],
    *,
    species: str | None,
    text_contains: str | None,
    min_subjects: int,
    exclude_synthetic: bool,
    group_by: list[str],
) -> dict[str, Any]:
    def keep(r: dict[str, Any]) -> bool:
        if species and (r.get("species") or "").lower() != species.lower():
            return False
        if r["n_subjects"] < min_subjects:
            return False
        if exclude_synthetic and r.get("synthetic"):
            return False
        if text_contains:
            needle = text_contains.lower()
            haystack = " ".join(
                str(r.get(k) or "") for k in ("name", "dx_status", "study_domain")
            ) + " " + " ".join(r.get("tasks") or []) + " " + " ".join((r.get("group_counts") or {}).keys())
            if needle not in haystack.lower():
                return False
        return True

    kept = [r for r in rows if keep(r)]
    aggregates: dict[str, Any] = {}
    for field in group_by:
        buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"datasets": 0, "subjects": 0})
        for r in kept:
            value = r.get(field)
            keys = value if isinstance(value, list) else [value]
            if field == "group_counts":
                for g, n in (r.get("group_counts") or {}).items():
                    buckets[g]["datasets"] += 1
                    buckets[g]["subjects"] += n
                continue
            for k in keys or [None]:
                label = str(k).strip() if k not in (None, "") else "(unknown)"
                buckets[label]["datasets"] += 1
                buckets[label]["subjects"] += r["n_subjects"]
        aggregates[field] = dict(sorted(buckets.items(), key=lambda kv: -kv[1]["subjects"]))
    return {
        "n_datasets": len(kept),
        "n_subjects": sum(r["n_subjects"] for r in kept),
        "aggregates": aggregates,
        "rows": sorted(kept, key=lambda r: -r["n_subjects"]),
    }


async def participant_count(client: OpenNeuroClient, modality: str | None) -> dict[str, Any]:
    data = await client.graphql(Q.PARTICIPANT_COUNT, {"modality": modality})
    return {"modality": modality or "all", "participants": data.get("participantCount")}


async def run_graphql(client: OpenNeuroClient, query: str, variables: dict[str, Any] | None) -> dict[str, Any]:
    """Run a read-only GraphQL document; mutations and subscriptions are refused."""
    try:
        doc = parse(query)
    except GraphQLSyntaxError as exc:
        raise OpenNeuroError(f"GraphQL syntax error: {exc.message} (line {exc.locations[0].line if exc.locations else '?'}).") from exc
    for definition in doc.definitions:
        if isinstance(definition, OperationDefinitionNode) and definition.operation != OperationType.QUERY:
            raise OpenNeuroError("Only read-only queries are allowed; mutations and subscriptions are refused.")
    return await client.graphql(query, variables)
