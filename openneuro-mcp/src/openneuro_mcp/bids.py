"""Helpers for BIDS text files (participants.tsv / participants.json)."""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from statistics import mean, median
from typing import Any

NA_VALUES = {"", "n/a", "na", "nan", "none", "null", "-", "?"}
MAX_LEVELS = 25  # columns with more distinct values are reported as free text / numeric


def parse_tsv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Parse a BIDS TSV file into (columns, rows). Tolerates a UTF-8 BOM and ragged rows."""
    text = text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    rows_raw = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows_raw:
        return [], []
    columns = [c.strip() for c in rows_raw[0]]
    rows = []
    for r in rows_raw[1:]:
        r = r + [""] * (len(columns) - len(r))
        rows.append({col: r[i].strip() for i, col in enumerate(columns)})
    return columns, rows


def parse_sidecar(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text.lstrip("﻿"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _as_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def summarize_column(name: str, values: list[str], sidecar: dict[str, Any]) -> dict[str, Any]:
    """Describe one participants.tsv column, joined with its participants.json entry."""
    meta = sidecar.get(name) if isinstance(sidecar.get(name), dict) else {}
    present = [v for v in values if v.strip().lower() not in NA_VALUES]
    info: dict[str, Any] = {
        "name": name,
        "description": meta.get("Description") or meta.get("LongName"),
        "units": meta.get("Units"),
        "n_missing": len(values) - len(present),
    }
    if meta.get("Levels"):
        info["levels"] = meta["Levels"]

    numbers = [_as_float(v) for v in present]
    all_numeric = bool(present) and all(n is not None for n in numbers)
    has_fractions = all_numeric and any(n != int(n) for n in numbers if n is not None)
    if all_numeric and (len(set(present)) > MAX_LEVELS // 2 or has_fractions):
        nums = [n for n in numbers if n is not None]
        info.update(
            type="numeric",
            min=min(nums),
            max=max(nums),
            mean=round(mean(nums), 3),
            median=round(median(nums), 3),
        )
        return info

    counts = Counter(present)
    if len(counts) <= MAX_LEVELS:
        info["type"] = "categorical"
        info["value_counts"] = dict(counts.most_common())
        levels = info.get("levels")
        if isinstance(levels, dict):
            lookup = {str(k).strip().lower(): str(label) for k, label in levels.items()}
            info["value_counts_labeled"] = {
                f"{k} ({lookup[k.lower()]})" if k.lower() in lookup else k: v for k, v in counts.most_common()
            }
    else:
        info["type"] = "text"
        info["n_unique"] = len(counts)
        info["examples"] = [v for v, _ in counts.most_common(5)]
    return info


_PREFIX_RE = re.compile(r"^sub-([A-Za-z]+)[-_]?\d+[A-Za-z]*$")


def id_prefix_groups(participant_ids: list[str]) -> dict[str, int] | None:
    """Detect group codes hidden in subject ids, e.g. sub-pd3 / sub-hc1 -> {'pd': 15, 'hc': 16}.

    Many datasets encode diagnosis only in the id. Returns None when ids carry no
    alphabetic prefix or every id shares the same one.
    """
    prefixes = []
    for pid in participant_ids:
        match = _PREFIX_RE.match(pid.strip())
        if not match:
            return None
        prefixes.append(match.group(1).lower())
    counts = Counter(prefixes)
    if len(counts) < 2:
        return None
    return dict(counts.most_common())


GROUP_COLUMN_HINTS = ("group", "diagnos", "dx", "condition", "status", "patient", "control", "cohort", "disease", "type", "arm")
NOT_GROUP_HINTS = ("duration", "onset", "age", "date", "time", "score", "dose", "severity", "years")


def likely_group_columns(columns: list[str]) -> list[str]:
    """Columns whose name suggests they hold diagnosis / group membership (not durations or scores)."""
    out = []
    for c in columns:
        name = c.lower()
        if c == "participant_id" or any(h in name for h in NOT_GROUP_HINTS):
            continue
        if any(h in name for h in GROUP_COLUMN_HINTS):
            out.append(c)
    return out
