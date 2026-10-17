"""A fake OpenNeuro GraphQL server.

Requests sent by the MCP server are executed by graphql-core against
tests/openneuro_schema.graphql (transcribed from the official schema), so a wrong
field name, argument or variable type fails the tests exactly as it would fail
against openneuro.org. Data comes from small in-memory fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from graphql import build_schema, graphql_sync

from openneuro_mcp.client import OpenNeuroClient

HERE = Path(__file__).parent
SCHEMA = build_schema((HERE / "openneuro_schema.graphql").read_text())
GRAPHQL_URL = "https://openneuro.test/crn/graphql"
S3 = "https://s3.amazonaws.com/openneuro.org"
FIX = HERE / "fixtures"


def _file(id_: str, name: str, size: int, *, directory: bool = False, annexed: bool = False, url: str | None = None):
    return {"id": id_, "filename": name, "size": size, "directory": directory, "annexed": annexed,
            "urls": [url] if url else []}


PD_TSV = (FIX / "ds002778_participants.tsv").read_text()
PD_JSON = (FIX / "ds002778_participants.json").read_text()

TREES: dict[str | None, list[dict[str, Any]]] = {
    None: [
        _file("t-sub-hc1", "sub-hc1", 0, directory=True),
        _file("f-desc", "dataset_description.json", 300, url=f"{S3}/ds002778/dataset_description.json?v=1"),
        _file("f-ptsv", "participants.tsv", len(PD_TSV), url=f"{S3}/ds002778/participants.tsv?v=1"),
        _file("f-pjson", "participants.json", len(PD_JSON), url=f"{S3}/ds002778/participants.json?v=1"),
    ],
    "t-sub-hc1": [_file("t-ses", "ses-hc", 0, directory=True)],
    "t-ses": [_file("t-eeg", "eeg", 0, directory=True)],
    "t-eeg": [
        _file("f-bdf", "sub-hc1_ses-hc_task-rest_eeg.bdf", 98_000_000, annexed=True,
              url=f"{S3}/ds002778/sub-hc1/ses-hc/eeg/sub-hc1_ses-hc_task-rest_eeg.bdf?v=1"),
        _file("f-ej", "sub-hc1_ses-hc_task-rest_eeg.json", 812,
              url=f"{S3}/ds002778/sub-hc1/ses-hc/eeg/sub-hc1_ses-hc_task-rest_eeg.json?v=1"),
    ],
}


def _summary(subjects: list[str], groups: list[str] | None = None, modalities=("eeg",), size=2_500_000_000):
    meta = [{"participantId": s, "age": 60.0 + i, "sex": "F" if i % 2 else "M", "group": (groups or [None] * len(subjects))[i]}
            for i, s in enumerate(subjects)]
    return {"id": "sum", "modalities": list(modalities), "primaryModality": modalities[0], "secondaryModalities": [],
            "subjects": subjects, "sessions": ["hc", "on", "off"], "tasks": ["rest"], "size": size, "totalFiles": 412,
            "dataProcessed": False, "subjectMetadata": meta}


PD_SUBJECTS = ["hc1", "hc2", "pd3", "pd5"]
SNAPSHOT_PD = {
    "id": "ds002778:1.0.5", "tag": "1.0.5", "created": "2021-01-01T00:00:00Z", "size": 2_500_000_000, "hexsha": "abc",
    "readme": "Resting state EEG from patients with Parkinson's disease ON and OFF medication and matched controls.",
    "description": json.loads((FIX / "ds002778_dataset_description.json").read_text()) | {"id": "d", "ReferencesAndLinks": ["https://doi.org/10.1093/brain/awaa000"]},
    "summary": _summary(PD_SUBJECTS, ["control", "control", "PD", "PD"]),
    "related": [{"id": "10.1093/brain/awaa000", "relation": "source", "kind": "Article", "description": None}],
    "files": lambda info, tree=None, recursive=None: TREES.get(tree, []),
}


def _dataset(id_, name, snapshot, meta):
    return {"id": id_, "name": name, "created": "2020-05-01T00:00:00Z", "public": True, "publishDate": "2020-06-01T00:00:00Z",
            "snapshots": [{"id": f"{id_}:1.0.0", "tag": "1.0.0"}, {"id": snapshot["id"], "tag": snapshot["tag"]}],
            "latestSnapshot": snapshot, "derivatives": [], "metadata": {"datasetId": id_} | meta}


DATASETS = {
    "ds002778": _dataset("ds002778", "UC San Diego Resting State EEG Data from Patients with Parkinson's Disease",
                         SNAPSHOT_PD, {"dxStatus": "Patient", "species": "Human", "studyDomain": "Parkinson's disease",
                                       "ages": [50.0, 82.0], "associatedPaperDOI": "10.1093/brain/awaa000",
                                       "syntheticDataset": False}),
    "ds000117": _dataset("ds000117", "Multisubject, multimodal face processing",
                         {"id": "ds000117:1.0.6", "tag": "1.0.6", "summary": _summary([f"{i:02d}" for i in range(1, 17)],
                                                                                    modalities=("mri", "meg", "eeg"), size=85_000_000_000)},
                         {"dxStatus": "Healthy / Control", "species": "Human", "studyDomain": "Face processing",
                          "ages": [23.0, 37.0], "syntheticDataset": False}),
    "ds009999": _dataset("ds009999", "Mouse auditory cortex",
                         {"id": "ds009999:1.0.0", "tag": "1.0.0", "summary": _summary(["m1", "m2"], ["ko", "wt"], modalities=("mri",))},
                         {"dxStatus": "Other", "species": "Mouse", "syntheticDataset": False}),
}
ORDER = ["ds002778", "ds000117", "ds009999"]


def _connection(ids: list[str], first: int | None, after: str | None):
    start = ORDER.index(after) + 1 if after else 0
    first = first or 25
    page = ids[start: start + first]
    return {"edges": [{"id": i, "cursor": i, "node": DATASETS[i]} for i in page],
            "pageInfo": {"hasNextPage": start + first < len(ids), "hasPreviousPage": start > 0,
                         "startCursor": page[0] if page else None, "endCursor": page[-1] if page else None,
                         "count": len(ids)}}


ROOT = {
    "dataset": lambda info, id: DATASETS.get(id),
    "snapshot": lambda info, datasetId, tag: SNAPSHOT_PD if (datasetId, tag) == ("ds002778", "1.0.5") else None,
    "participantCount": lambda info, modality=None: 31 if (modality or "").lower() == "eeg" else 50_000,
    "datasets": lambda info, first=25, after=None, modality=None, **_: _connection(
        [i for i in ORDER if not modality or modality in DATASETS[i]["latestSnapshot"]["summary"]["modalities"]], first, after),
    "advancedSearch": lambda info, query, first=None, after=None, **_: _connection(
        [i for i in ORDER if any(k.lower() in DATASETS[i]["name"].lower() for k in query.get("keywords") or [""])], first, after),
    "publicMetadata": lambda info: [d["metadata"] for d in DATASETS.values()],
}


class FakeOpenNeuro:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        result = graphql_sync(SCHEMA, body["query"], root_value=ROOT, variable_values=body.get("variables"))
        out: dict[str, Any] = {"data": result.data}
        if result.errors:
            out["errors"] = [{"message": e.message} for e in result.errors]
        return httpx.Response(200, json=out)


@pytest.fixture
def fake_api():
    fake = FakeOpenNeuro()
    with respx.mock(assert_all_called=False) as router:
        router.post(GRAPHQL_URL).mock(side_effect=fake)
        router.get(url__startswith=f"{S3}/ds002778/participants.tsv").mock(return_value=httpx.Response(200, text=PD_TSV))
        router.get(url__startswith=f"{S3}/ds002778/participants.json").mock(return_value=httpx.Response(200, text=PD_JSON))
        router.get(url__startswith=f"{S3}/ds002778/sub-hc1/ses-hc/eeg/sub-hc1_ses-hc_task-rest_eeg.json").mock(
            return_value=httpx.Response(200, json={"TaskName": "rest", "SamplingFrequency": 512}))
        router.get(url__startswith=f"{S3}/ds002778/sub-hc1/ses-hc/eeg/sub-hc1_ses-hc_task-rest_eeg.bdf").mock(
            return_value=httpx.Response(200, content=b"\x00\x01BIOSEMI" + b"\x00" * 100))
        yield fake


@pytest.fixture
async def client():
    c = OpenNeuroClient(graphql_url=GRAPHQL_URL, backend="auto")
    yield c
    await c.aclose()
