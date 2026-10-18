"""OpenNeuro MCP server: search, census, participants, files and downloads for OpenNeuro datasets."""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import Field

from . import service as S
from .client import OpenNeuroClient, OpenNeuroError

try:  # MCP Python SDK v2
    from mcp.server import MCPServer
except ImportError:  # MCP Python SDK v1
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[no-redef]
from mcp.types import ToolAnnotations

INSTRUCTIONS = """\
Tools for OpenNeuro (openneuro.org), the open archive of BIDS-formatted MRI, fMRI, EEG, MEG, iEEG
and PET datasets. Typical workflow:
1. openneuro_census for the whole-archive picture (counts by modality, diagnosis status, species,
   or per-participant group labels), or openneuro_search_datasets for targeted searches.
2. openneuro_get_dataset for one dataset's description, versions, paper DOI and validator summary.
3. openneuro_get_participants to see who is in it: columns, the data dictionary from
   participants.json, likely diagnosis/group columns and group codes hidden in subject ids.
4. openneuro_list_files / openneuro_read_file for sidecar JSON, events.tsv, README, phenotype files.
5. openneuro_get_download_info before fetching imaging data (sizes and download commands).
Everything is read-only. Dataset ids look like 'ds002778'.
"""

logging.getLogger("httpx").setLevel(logging.WARNING)  # keep stderr quiet; one line per request is noise

mcp = MCPServer("openneuro_mcp", instructions=INSTRUCTIONS)
client = OpenNeuroClient()

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)


class Format(str, Enum):
    markdown = "markdown"
    json = "json"


FormatArg = Annotated[Format, Field(description="'markdown' (readable) or 'json' (complete, for programs).")]
DatasetIdArg = Annotated[str, Field(description="OpenNeuro dataset id, e.g. 'ds002778'.", min_length=3, max_length=12)]
TagArg = Annotated[str | None, Field(description="Snapshot version tag, e.g. '1.0.0'. Omit for the latest version.")]


# ---------------------------------------------------------------- formatting helpers
def _size(n: int | None) -> str:
    if n is None:
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return "?"


def _join(items: list[Any] | None, limit: int = 8) -> str:
    items = [str(i) for i in (items or []) if i not in (None, "")]
    if not items:
        return "—"
    extra = f" (+{len(items) - limit})" if len(items) > limit else ""
    return ", ".join(items[:limit]) + extra


def _dump(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _error(exc: Exception) -> str:
    if isinstance(exc, OpenNeuroError):
        return f"Error: {exc}"
    return f"Error: unexpected {type(exc).__name__}: {exc}"


def _dataset_line(r: dict[str, Any]) -> str:
    return (
        f"- **{r['id']}** — {r.get('name') or '(no name)'}\n"
        f"  {_join(r.get('modalities'))} · {r['n_subjects']} subjects · {_size(r.get('size_bytes'))}"
        f" · dx: {r.get('dx_status') or '—'} · species: {r.get('species') or '—'}"
        + (f" · tasks: {_join(r.get('tasks'), 4)}" if r.get("tasks") else "")
        + (f" · paper: {r['paper_doi']}" if r.get("paper_doi") else "")
    )


# ---------------------------------------------------------------- tools
@mcp.tool(name="openneuro_search_datasets", annotations=READ_ONLY)
async def openneuro_search_datasets(
    keywords: Annotated[list[str] | None, Field(description="Free-text terms, e.g. ['parkinson', 'resting state'].")] = None,
    modality: Annotated[str | None, Field(description="One modality, case-insensitive: 'eeg', 'meg', 'mri', 'ieeg' or 'pet'.")] = None,
    diagnosis: Annotated[str | None, Field(description="Diagnosis status filter as indexed by OpenNeuro, e.g. 'Healthy / Control' or 'Patient'.")] = None,
    tasks: Annotated[list[str] | None, Field(description="BIDS task names, e.g. ['rest'].")] = None,
    species: Annotated[str | None, Field(description="e.g. 'Human', 'Mouse', 'Rat'.")] = None,
    age_min: Annotated[int | None, Field(ge=0, le=150)] = None,
    age_max: Annotated[int | None, Field(ge=0, le=150)] = None,
    subjects_min: Annotated[int | None, Field(ge=0, description="Minimum number of subjects.")] = None,
    subjects_max: Annotated[int | None, Field(ge=0)] = None,
    sort: Annotated[Literal["relevance", "newest", "oldest", "activity", "name_asc", "name_desc", "last_updated"], Field()] = "relevance",
    limit: Annotated[int, Field(ge=1, le=100, description="Results per page.")] = 20,
    cursor: Annotated[str | None, Field(description="next_cursor from a previous call, to get the next page.")] = None,
    response_format: FormatArg = Format.markdown,
) -> str:
    """Search OpenNeuro datasets with keyword and structured filters (modality, diagnosis, task, species, age, size).

    Returns one row per dataset: id, name, modalities, number of subjects, size, diagnosis status,
    species, tasks and associated paper DOI, plus `next_cursor` for pagination. Use
    openneuro_census instead when you need counts over the whole archive.
    """
    try:
        res = await S.search_datasets(
            client, keywords=keywords, modality=modality, diagnosis=diagnosis, tasks=tasks, species=species,
            age_min=age_min, age_max=age_max, subjects_min=subjects_min, subjects_max=subjects_max,
            sort=sort, limit=limit, cursor=cursor,
        )
    except Exception as exc:  # noqa: BLE001 - every failure is reported to the agent
        return _error(exc)
    if response_format == Format.json:
        return _dump(res)
    if not res["datasets"]:
        return "No datasets matched. Loosen the filters (e.g. drop diagnosis or tasks) or try other keywords."
    lines = [f"# OpenNeuro search ({res['count']} shown" + (f" of {res['total']}" if res.get("total") else "") + ")", ""]
    lines += [_dataset_line(r) for r in res["datasets"]]
    if res["next_cursor"]:
        lines += ["", f"More results: call again with cursor='{res['next_cursor']}'."]
    return "\n".join(lines)


@mcp.tool(name="openneuro_get_dataset", annotations=READ_ONLY)
async def openneuro_get_dataset(
    dataset_id: DatasetIdArg,
    tag: TagArg = None,
    include_readme: Annotated[bool, Field(description="Include the README text.")] = True,
    readme_chars: Annotated[int, Field(ge=200, le=50_000)] = 4000,
    response_format: FormatArg = Format.markdown,
) -> str:
    """Get one dataset's overview: name, versions, modalities, subjects, tasks, size, diagnosis status,
    group labels reported by the BIDS validator, age range, license, authors, funding, DOIs,
    related papers, available derivatives (e.g. fMRIPrep) and README.

    Falls back to the OpenNeuroDatasets GitHub mirror when openneuro.org is unreachable
    (`source` tells which was used).
    """
    try:
        res = await S.get_dataset(client, dataset_id, tag=tag, include_readme=include_readme, readme_chars=readme_chars)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if response_format == Format.json:
        return _dump(res)
    desc = res.get("description") or {}
    meta = res.get("metadata") or {}
    lines = [f"# {res['id']} — {res.get('name') or '(no name)'}", f"{res['url']} · source: {res['source']}"]
    if res.get("note"):
        lines.append(f"_{res['note']}_")
    lines.append("")
    if res["source"] == "graphql":
        lines += [
            f"- **Version**: {res.get('tag')} (all: {_join(res.get('versions'), 10)})",
            f"- **Modalities**: {_join(res.get('modalities'))} · **Subjects**: {res.get('n_subjects')}"
            f" · **Sessions**: {res.get('n_sessions')} · **Size**: {_size(res.get('size_bytes'))}",
            f"- **Tasks**: {_join(res.get('tasks'), 12)}",
            f"- **Diagnosis status**: {meta.get('dxStatus') or '—'} · **Species**: {meta.get('species') or '—'}"
            f" · **Domain**: {meta.get('studyDomain') or '—'}",
            f"- **Groups (validator)**: {res.get('groups_from_validator') or '—'} · **Sex**: {res.get('sex_counts') or '—'}"
            f" · **Age range**: {res.get('age_range') or '—'}",
            f"- **Paper DOI**: {meta.get('associatedPaperDOI') or '—'} · **Dataset DOI**: {desc.get('DatasetDOI') or '—'}",
            f"- **Derivatives**: {_join([d.get('name') for d in res.get('derivatives') or []])}",
        ]
    else:
        lines.append(f"- **Subjects (participants.tsv)**: {res.get('n_subjects', '?')} · **Latest version**: {res.get('latest_version_line', '?')}")
    lines += [
        f"- **License**: {desc.get('License') or '—'} · **Authors**: {_join(desc.get('Authors'), 6)}",
        f"- **References**: {_join(desc.get('ReferencesAndLinks'), 5)}",
        f"- **Funding**: {_join(desc.get('Funding'), 4)}",
    ]
    if res.get("related"):
        lines.append("- **Related**: " + _join([f"{r['kind']} {r['id']} ({r['relation']})" for r in res["related"]], 6))
    if res.get("readme"):
        lines += ["", "## README", res["readme"] + (" …[truncated]" if res.get("readme_truncated") else "")]
    return "\n".join(lines)


@mcp.tool(name="openneuro_get_participants", annotations=READ_ONLY)
async def openneuro_get_participants(
    dataset_id: DatasetIdArg,
    tag: TagArg = None,
    max_rows: Annotated[int, Field(ge=0, le=1000, description="Raw rows to return (0 = summary only).")] = 50,
    offset: Annotated[int, Field(ge=0)] = 0,
    response_format: FormatArg = Format.markdown,
) -> str:
    """Describe who is in a dataset, from participants.tsv joined with its participants.json data dictionary.

    For every column: description, units, coded levels (e.g. {'1': 'Parkinson'}), value counts or
    numeric range, and missing values. Also flags `likely_group_columns` (group, diagnosis, dx...)
    and `id_prefix_groups`, i.e. diagnosis codes hidden in subject ids such as sub-pd03 / sub-hc01.
    Use this to decide how each participant should be labelled (patient vs control, condition, drug).
    """
    try:
        res = await S.get_participants(client, dataset_id, tag=tag, max_rows=max_rows, offset=offset)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if response_format == Format.json:
        return _dump(res)
    if not res.get("found"):
        return res["message"]
    lines = [
        f"# Participants of {res['id']} ({res['tag']}, source: {res['source']})",
        f"- **N** = {res['n_participants']} · data dictionary (participants.json): {'yes' if res['has_data_dictionary'] else 'no'}",
        f"- **Likely group/diagnosis columns**: {_join(res['likely_group_columns']) }",
        f"- **Group codes in subject ids**: {res['id_prefix_groups'] or '—'}",
        "",
        "## Columns",
    ]
    for col in res["columns"]:
        head = f"- **{col['name']}** ({col.get('type', '?')}, missing {col['n_missing']})"
        if col.get("description"):
            head += f" — {col['description']}"
        if col.get("units"):
            head += f" [{col['units']}]"
        lines.append(head)
        if col.get("value_counts_labeled") or col.get("value_counts"):
            lines.append(f"  counts: {col.get('value_counts_labeled') or col.get('value_counts')}")
        elif col.get("type") == "numeric":
            lines.append(f"  range {col['min']}–{col['max']}, mean {col['mean']}, median {col['median']}")
        elif col.get("examples"):
            lines.append(f"  {col['n_unique']} unique, e.g. {_join(col['examples'], 5)}")
    if res["rows"]:
        cols = list(res["rows"][0].keys())[:8]
        lines += ["", f"## Rows {res['rows_offset']}–{res['rows_offset'] + len(res['rows']) - 1}",
                  "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        lines += ["| " + " | ".join(r.get(c, "") for c in cols) + " |" for r in res["rows"]]
        if res["has_more_rows"]:
            lines.append(f"\nMore rows: offset={res['rows_offset'] + len(res['rows'])}.")
    return "\n".join(lines)


@mcp.tool(name="openneuro_list_files", annotations=READ_ONLY)
async def openneuro_list_files(
    dataset_id: DatasetIdArg,
    path: Annotated[str, Field(description="Folder inside the dataset, e.g. '' (root), 'sub-01', 'sub-01/eeg', 'derivatives'.")] = "",
    tag: TagArg = None,
    limit: Annotated[int, Field(ge=1, le=500)] = 100,
    offset: Annotated[int, Field(ge=0)] = 0,
    response_format: FormatArg = Format.markdown,
) -> str:
    """List the files and folders in one folder of a dataset snapshot, with sizes and download URLs.

    Folders come first. `annexed: true` marks large binary files stored on S3. Navigate by passing
    a deeper `path`. Requires the OpenNeuro API.
    """
    try:
        res = await S.list_files(client, dataset_id, path=path, tag=tag, limit=limit, offset=offset)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if response_format == Format.json:
        return _dump(res)
    lines = [
        f"# {res['id']}@{res['tag']}:/{res['path'].lstrip('/')}",
        f"{res['n_folders']} folders, {res['n_files']} files ({_size(res['files_size_bytes'])} in files at this level)",
        "",
    ]
    for e in res["entries"]:
        if e["type"] == "folder":
            lines.append(f"- {e['name']}/")
        else:
            lines.append(f"- {e['name']} — {_size(e['size_bytes'])}" + (" (annexed)" if e.get("annexed") else ""))
    if res["has_more"]:
        lines.append(f"\nMore entries: offset={res['offset'] + len(res['entries'])}.")
    return "\n".join(lines)


@mcp.tool(name="openneuro_read_file", annotations=READ_ONLY)
async def openneuro_read_file(
    dataset_id: DatasetIdArg,
    path: Annotated[str, Field(description="File path inside the dataset, e.g. 'participants.json', 'task-rest_eeg.json', 'sub-01/eeg/sub-01_task-rest_events.tsv'.")],
    tag: TagArg = None,
    max_chars: Annotated[int, Field(ge=100, le=200_000)] = 20_000,
) -> str:
    """Read a small text file from a dataset (JSON sidecars, TSV tables, README, CHANGES, phenotype files).

    Binary imaging files (NIfTI, EDF, FIF, BDF...) are refused; use openneuro_get_download_info for
    those. Falls back to the GitHub mirror (latest version) when openneuro.org is unreachable.
    """
    try:
        res = await S.read_file(client, dataset_id, path=path, tag=tag, max_chars=max_chars)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    note = " …[truncated; raise max_chars to read more]" if res["truncated"] else ""
    return f"# {res['id']}/{res['path']} ({res['tag']}, source: {res['source']})\n\n{res['text']}{note}"


@mcp.tool(name="openneuro_get_download_info", annotations=READ_ONLY)
async def openneuro_get_download_info(
    dataset_id: DatasetIdArg,
    include: Annotated[str | None, Field(description="Optional glob to download only part of the dataset, e.g. 'sub-*/eeg/*task-rest*'.")] = None,
    response_format: FormatArg = Format.markdown,
) -> str:
    """Get the size of a dataset and ready-to-run commands to download it (openneuro-py, DataLad, AWS S3),
    plus any precomputed derivatives. This tool never downloads anything itself.
    """
    try:
        res = await S.get_download_info(client, dataset_id, include=include)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    if response_format == Format.json:
        return _dump(res)
    lines = [f"# Download {res['id']}" + (f" — {res['name']}" if res.get("name") else "")]
    if res.get("note"):
        lines.append(f"_{res['note']}_")
    if res.get("size_bytes") is not None:
        lines.append(f"- Version {res.get('tag')} · {_size(res['size_bytes'])} · {res.get('total_files')} files · "
                     f"{res.get('n_subjects')} subjects · {_join(res.get('modalities'))}")
    if res.get("derivatives"):
        lines.append("- Derivatives: " + _join([f"{d.get('name')} ({d.get('s3Url') or d.get('dataladUrl')})" for d in res["derivatives"]], 6))
    lines += ["", "```bash"] + [f"# {k}\n{v}" for k, v in res["commands"].items()] + ["```", "", res["advice"]]
    return "\n".join(lines)


@mcp.tool(name="openneuro_census", annotations=READ_ONLY)
async def openneuro_census(
    modality: Annotated[str | None, Field(description="Restrict to one modality, case-insensitive: 'eeg', 'meg', 'mri', 'ieeg', 'pet'. Omit for all.")] = None,
    species: Annotated[str | None, Field(description="Keep only this species, e.g. 'Human'.")] = None,
    text_contains: Annotated[str | None, Field(description="Keep datasets whose name, diagnosis status, domain, tasks or group labels contain this text, e.g. 'parkinson'.")] = None,
    min_subjects: Annotated[int, Field(ge=0)] = 0,
    exclude_synthetic: bool = True,
    include_groups: Annotated[bool, Field(description="Also fetch per-participant group labels from the BIDS validator (slower, enables group_by=['group_counts']).")] = False,
    group_by: Annotated[list[Literal["modalities", "primary_modality", "dx_status", "species", "study_domain", "tasks", "group_counts"]], Field(description="Fields to aggregate datasets and subjects by.")] = ["modalities", "dx_status"],
    limit: Annotated[int, Field(ge=0, le=500, description="Dataset rows to return, largest first (0 = aggregates only).")] = 25,
    offset: Annotated[int, Field(ge=0)] = 0,
    max_datasets: Annotated[int, Field(ge=1, le=10_000, description="Safety cap on datasets fetched.")] = 5000,
    refresh: Annotated[bool, Field(description="Ignore the 6-hour cache and refetch.")] = False,
    response_format: FormatArg = Format.markdown,
) -> str:
    """Census of the public OpenNeuro archive: one row per dataset (subjects, modalities, diagnosis
    status, species, tasks, ages, paper DOI, optional per-participant group counts) plus aggregate
    counts of datasets and subjects by the requested fields.

    The first call pages through the whole archive (can take a minute); results are cached for 6 hours,
    so follow-up calls with different filters, group_by or offset are instant.
    """
    try:
        rows = await S.census(client, modality=modality, include_groups=include_groups or "group_counts" in group_by,
                              refresh=refresh, max_datasets=max_datasets)
        res = S.filter_and_aggregate(rows, species=species, text_contains=text_contains, min_subjects=min_subjects,
                                     exclude_synthetic=exclude_synthetic, group_by=group_by)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    page = res["rows"][offset: offset + limit]
    payload = {k: v for k, v in res.items() if k != "rows"}
    payload.update(fetched_datasets=len(rows), offset=offset, has_more=offset + limit < len(res["rows"]), rows=page)
    if response_format == Format.json:
        return _dump(payload)
    lines = [
        f"# OpenNeuro census ({modality or 'all modalities'})",
        f"{res['n_datasets']} datasets · {res['n_subjects']} subjects after filters (fetched {len(rows)}).",
    ]
    for field, buckets in res["aggregates"].items():
        lines += ["", f"## By {field}", "| value | datasets | subjects |", "|---|---|---|"]
        lines += [f"| {k} | {v['datasets']} | {v['subjects']} |" for k, v in list(buckets.items())[:30]]
        if len(buckets) > 30:
            lines.append(f"| … {len(buckets) - 30} more (use response_format='json') | | |")
    if page:
        lines += ["", f"## Largest datasets ({offset}–{offset + len(page) - 1})"] + [_dataset_line(r) for r in page]
    return "\n".join(lines)


@mcp.tool(name="openneuro_count_participants", annotations=READ_ONLY)
async def openneuro_count_participants(
    modality: Annotated[str | None, Field(description="e.g. 'EEG'. Omit for all modalities.")] = None,
) -> str:
    """Total number of participants across all public OpenNeuro datasets, optionally for one modality (fast)."""
    try:
        res = await S.participant_count(client, modality)
    except Exception as exc:  # noqa: BLE001
        return _error(exc)
    return f"{res['participants']} participants in public OpenNeuro datasets ({res['modality']})."


@mcp.tool(name="openneuro_graphql", annotations=READ_ONLY)
async def openneuro_graphql(
    query: Annotated[str, Field(description="A read-only GraphQL query document.", min_length=3, max_length=20_000)],
    variables: Annotated[dict[str, Any] | None, Field(description="Variables for the query.")] = None,
) -> str:
    """Escape hatch: run any read-only GraphQL query against the OpenNeuro API for fields the other
    tools do not cover (e.g. dataset analytics, validation issues, contributors). Mutations are refused.
    Prefer the dedicated tools; they handle pagination, fallbacks and formatting.
    """
    try:
        return _dump(await S.run_graphql(client, query, variables))
    except Exception as exc:  # noqa: BLE001
        return _error(exc)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="OpenNeuro MCP server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--port", type=int, default=8000, help="Port for streamable-http.")
    args = parser.parse_args()
    if args.transport == "stdio":
        mcp.run()
    else:
        try:
            mcp.run(transport="streamable-http", port=args.port)
        except TypeError:  # SDK v1 reads the port from settings
            mcp.settings.port = args.port  # type: ignore[attr-defined]
            mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
