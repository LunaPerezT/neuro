"""Tool logic against the fake OpenNeuro server (real schema, fixture data)."""

from __future__ import annotations

import pytest
from graphql import build_schema, parse, validate

from openneuro_mcp import queries as Q
from openneuro_mcp import service as S
from openneuro_mcp.bids import id_prefix_groups, parse_tsv
from openneuro_mcp.client import OpenNeuroError, normalize_dataset_id, safe_relative_path

from .conftest import HERE, PD_TSV


@pytest.mark.parametrize("name", sorted(Q.ALL_DOCUMENTS))
def test_every_query_is_valid_against_official_schema(name):
    schema = build_schema((HERE / "openneuro_schema.graphql").read_text())
    assert validate(schema, parse(Q.ALL_DOCUMENTS[name])) == []


def test_dataset_id_normalisation():
    assert normalize_dataset_id("DS2778") == "ds002778"
    assert normalize_dataset_id(" ds002778 ") == "ds002778"
    with pytest.raises(OpenNeuroError):
        normalize_dataset_id("parkinson")


def test_path_traversal_refused():
    assert safe_relative_path("/sub-01//eeg/") == "sub-01/eeg"
    with pytest.raises(OpenNeuroError):
        safe_relative_path("../secrets")


def test_real_participants_file_reveals_groups_in_ids():
    _, rows = parse_tsv(PD_TSV)
    groups = id_prefix_groups([r["participant_id"] for r in rows])
    assert groups == {"hc": 16, "pd": 15}


async def test_search(fake_api, client):
    res = await S.search_datasets(client, keywords=["parkinson"], modality="EEG", diagnosis=None, tasks=["rest"],
                                  species="Human", age_min=40, age_max=None, subjects_min=10, subjects_max=None,
                                  sort="relevance", limit=10, cursor=None)
    assert [d["id"] for d in res["datasets"]] == ["ds002778"]
    row = res["datasets"][0]
    assert row["n_subjects"] == 4 and row["dx_status"] == "Patient" and row["paper_doi"]
    sent = fake_api.requests[-1]["variables"]["query"]
    assert sent["modality"] == "eeg"
    assert sent["ageRange"] == [40, 150] and sent["subjectCountRange"][0] == 10


async def test_get_dataset_latest_and_tag(fake_api, client):
    res = await S.get_dataset(client, "ds002778", tag=None, include_readme=True, readme_chars=500)
    assert res["source"] == "graphql" and res["tag"] == "1.0.5"
    assert res["groups_from_validator"] == {"control": 2, "PD": 2}
    assert res["versions"] == ["1.0.0", "1.0.5"] and res["description"]["License"] == "CC0"
    tagged = await S.get_dataset(client, "ds002778", tag="1.0.5", include_readme=False, readme_chars=500)
    assert tagged["tag"] == "1.0.5" and "readme" not in tagged
    with pytest.raises(OpenNeuroError, match="no snapshot"):
        await S.get_dataset(client, "ds002778", tag="9.9.9", include_readme=False, readme_chars=500)
    with pytest.raises(OpenNeuroError, match="not found"):
        await S.get_dataset(client, "ds000001", tag=None, include_readme=False, readme_chars=500)


async def test_participants_with_data_dictionary(fake_api, client):
    res = await S.get_participants(client, "ds002778", tag=None, max_rows=5, offset=0)
    assert res["found"] and res["n_participants"] == 31 and res["has_data_dictionary"]
    assert res["id_prefix_groups"] == {"hc": 16, "pd": 15}
    cols = {c["name"]: c for c in res["columns"]}
    assert cols["age"]["units"] == "years" and cols["age"]["type"] == "numeric"
    assert "f (female)" in cols["gender"]["value_counts_labeled"]
    assert len(res["rows"]) == 5 and res["has_more_rows"]


async def test_list_and_read_files(fake_api, client):
    root = await S.list_files(client, "ds002778", path="", tag=None, limit=50, offset=0)
    assert root["entries"][0]["type"] == "folder" and root["n_files"] == 3
    eeg = await S.list_files(client, "ds002778", path="sub-hc1/ses-hc/eeg", tag=None, limit=50, offset=0)
    assert {e["name"] for e in eeg["entries"]} == {"sub-hc1_ses-hc_task-rest_eeg.bdf", "sub-hc1_ses-hc_task-rest_eeg.json"}
    with pytest.raises(OpenNeuroError, match="does not exist"):
        await S.list_files(client, "ds002778", path="sub-zz", tag=None, limit=50, offset=0)
    sidecar = await S.read_file(client, "ds002778", path="sub-hc1/ses-hc/eeg/sub-hc1_ses-hc_task-rest_eeg.json",
                                tag=None, max_chars=1000)
    assert "SamplingFrequency" in sidecar["text"]
    with pytest.raises(OpenNeuroError, match="binary"):
        await S.read_file(client, "ds002778", path="sub-hc1/ses-hc/eeg/sub-hc1_ses-hc_task-rest_eeg.bdf",
                          tag=None, max_chars=1000)


async def test_download_info(fake_api, client):
    res = await S.get_download_info(client, "ds002778", include="sub-*/ses-*/eeg/*rest*")
    assert res["size_bytes"] == 2_500_000_000 and res["tag"] == "1.0.5"
    assert "--include 'sub-*/ses-*/eeg/*rest*'" in res["commands"]["openneuro-py"]
    assert res["commands"]["aws_s3"].startswith("aws s3 sync --no-sign-request s3://openneuro.org/ds002778")


async def test_census_paginates_and_aggregates(fake_api, client, monkeypatch):
    monkeypatch.setattr(S, "CENSUS_PAGE_SIZE", 2)
    monkeypatch.setattr(S, "CENSUS_GROUPS_PAGE_SIZE", 2)
    rows = await S.census(client, modality=None, include_groups=True, refresh=True, max_datasets=100)
    assert [r["id"] for r in rows] == ["ds002778", "ds000117", "ds009999"]
    n_calls = len(fake_api.requests)
    assert n_calls == 2  # two pages of size 2
    again = await S.census(client, modality=None, include_groups=True, refresh=False, max_datasets=100)
    assert again == rows and len(fake_api.requests) == n_calls  # served from cache
    agg = S.filter_and_aggregate(rows, species="Human", text_contains=None, min_subjects=0,
                                 exclude_synthetic=True, group_by=["modalities", "group_counts"])
    assert agg["n_datasets"] == 2 and agg["n_subjects"] == 20
    assert agg["aggregates"]["modalities"]["eeg"] == {"datasets": 2, "subjects": 20}
    assert agg["aggregates"]["group_counts"]["pd"] == {"datasets": 1, "subjects": 2}
    pd_only = S.filter_and_aggregate(rows, species=None, text_contains="parkinson", min_subjects=0,
                                     exclude_synthetic=True, group_by=[])
    assert [r["id"] for r in pd_only["rows"]] == ["ds002778"]


async def test_census_modality_filter(fake_api, client):
    rows = await S.census(client, modality="MEG",  # upper case must work too
                            include_groups=False, refresh=True, max_datasets=100)
    assert [r["id"] for r in rows] == ["ds000117"]


async def test_graphql_escape_hatch_is_read_only(fake_api, client):
    data = await S.run_graphql(client, '{ participantCount(modality: "EEG") }', None)
    assert data == {"participantCount": 31}
    with pytest.raises(OpenNeuroError, match="read-only"):
        await S.run_graphql(client, "mutation { deleteDataset(id: \"ds000001\") }", None)
    with pytest.raises(OpenNeuroError, match="syntax"):
        await S.run_graphql(client, "{ dataset(id: ", None)


async def test_graphql_errors_are_reported(fake_api, client):
    with pytest.raises(OpenNeuroError, match="Cannot query field"):
        await S.run_graphql(client, "{ notAField }", None)
