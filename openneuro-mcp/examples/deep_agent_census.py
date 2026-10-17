"""Deep agent that uses the OpenNeuro MCP server to rank conditions by available public data.

Run:
    pip install deepagents langchain-mcp-adapters langchain-anthropic openneuro-mcp
    export ANTHROPIC_API_KEY=...          # or change MODEL to another provider
    export LANGSMITH_API_KEY=...          # optional: traces every step in LangSmith
    export LANGSMITH_TRACING=true
    python examples/deep_agent_census.py
"""

from __future__ import annotations

import asyncio
import os

from deepagents import create_deep_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

MODEL = "anthropic:claude-sonnet-5-5"

SYSTEM_PROMPT = """\
You are a neuroscience data curator. Use the OpenNeuro tools to answer with numbers, never guesses.
1. Start with openneuro_census (modality and group_by as needed) to get archive-wide counts.
2. For the most promising datasets, call openneuro_get_participants to check how patients and
   controls are labelled (data dictionary, group columns, codes hidden in subject ids).
3. Record every dataset you inspect in /notes/datasets.md: id, modality, N patients, N controls,
   how the label was derived, paper DOI.
4. Finish with a ranked table of conditions by total participants with matched controls.
"""

CURATOR = {
    "name": "participant-curator",
    "description": "Inspects one OpenNeuro dataset and returns how many patients/controls it has and how they are labelled.",
    "system_prompt": "Given a dataset id, call openneuro_get_participants and openneuro_get_dataset, then return "
                     "a short JSON with n_patients, n_controls, condition, label_source and caveats.",
}


async def main() -> None:
    mcp_client = MultiServerMCPClient(
        # env: the MCP stdio launcher passes only a minimal environment by default; forwarding it keeps
        # proxy settings (HTTPS_PROXY, certificates) and OPENNEURO_* options working.
        {"openneuro": {"command": "openneuro-mcp", "args": [], "transport": "stdio", "env": dict(os.environ)}}
    )
    tools = await mcp_client.get_tools()
    agent = create_deep_agent(
        model=MODEL,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        subagents=[{**CURATOR, "tools": tools}],
    )
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content":
            "Which neurological or psychiatric conditions have the most public resting-state EEG data "
            "on OpenNeuro, counting only datasets that also include healthy controls?"}]}
    )
    print(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main())
