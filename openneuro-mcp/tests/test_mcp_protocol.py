"""End-to-end over the MCP protocol: list tools and call them through an MCP client."""

from __future__ import annotations

import mcp
import pytest

from openneuro_mcp import server

from .conftest import GRAPHQL_URL

mcp_client = getattr(mcp, "Client", None)  # in-process client exists in SDK v2

EXPECTED_TOOLS = {
    "openneuro_search_datasets", "openneuro_get_dataset", "openneuro_get_participants", "openneuro_list_files",
    "openneuro_read_file", "openneuro_get_download_info", "openneuro_census", "openneuro_count_participants",
    "openneuro_graphql",
}


def _text(result) -> str:
    return "".join(getattr(c, "text", "") for c in result.content)


@pytest.fixture(autouse=True)
def point_server_at_fake(monkeypatch):
    monkeypatch.setattr(server.client, "graphql_url", GRAPHQL_URL)
    server.client._cache.clear()


@pytest.mark.skipif(mcp_client is None, reason="in-process Client needs MCP SDK v2")
async def test_tools_are_listed_with_read_only_annotations():
    async with mcp_client(server.mcp) as c:
        tools = (await c.list_tools()).tools
    assert {t.name for t in tools} == EXPECTED_TOOLS
    for t in tools:
        assert t.annotations.read_only_hint is True or t.annotations.readOnlyHint is True
        assert t.description and len(t.description) > 40


@pytest.mark.skipif(mcp_client is None, reason="in-process Client needs MCP SDK v2")
async def test_call_tools_over_protocol(fake_api):
    async with mcp_client(server.mcp) as c:
        participants = _text(await c.call_tool("openneuro_get_participants", {"dataset_id": "ds2778", "max_rows": 3}))
        assert "Group codes in subject ids**: {'hc': 16, 'pd': 15}" in participants
        assert "| participant_id |" in participants

        census = _text(await c.call_tool("openneuro_census", {"group_by": ["modalities"], "limit": 2}))
        assert "| eeg | 2 | 20 |" in census

        files = _text(await c.call_tool("openneuro_list_files", {"dataset_id": "ds002778", "path": "sub-hc1/ses-hc/eeg"}))
        assert "(annexed)" in files

        bad = _text(await c.call_tool("openneuro_get_dataset", {"dataset_id": "not-an-id"}))
        assert bad.startswith("Error:") and "ds002778" in bad
