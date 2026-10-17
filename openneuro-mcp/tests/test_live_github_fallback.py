"""Live test of the GitHub-mirror fallback (needs raw.githubusercontent.com; run with -m live)."""

from __future__ import annotations

import pytest

from openneuro_mcp import service as S
from openneuro_mcp.client import OpenNeuroClient

pytestmark = pytest.mark.live


@pytest.fixture
async def offline_api_client():
    # An unroutable GraphQL endpoint forces the fallback path.
    c = OpenNeuroClient(graphql_url="https://openneuro.invalid/crn/graphql", backend="auto", timeout=15)
    yield c
    await c.aclose()


async def test_fallback_dataset_and_participants(offline_api_client):
    ds = await S.get_dataset(offline_api_client, "ds002778", tag=None, include_readme=True, readme_chars=300)
    assert ds["source"] == "github-mirror" and "Parkinson" in ds["name"]
    assert ds["n_subjects"] == 31

    p = await S.get_participants(offline_api_client, "ds002778", tag=None, max_rows=0, offset=0)
    assert p["source"] == "github-mirror" and p["id_prefix_groups"] == {"hc": 16, "pd": 15}
    assert p["has_data_dictionary"]

    f = await S.read_file(offline_api_client, "ds002778", path="dataset_description.json", tag=None, max_chars=2000)
    assert '"BIDSVersion"' in f["text"]
