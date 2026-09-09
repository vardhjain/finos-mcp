"""LangGraph agent over the three finos-mcp servers.

Run it in its own environment, **not** the workspace venv. Run from outside the repository
so uv cannot discover the workspace `.venv` and layer onto it::

    export ANTHROPIC_API_KEY=...
    cd /tmp && uv run --no-project --with langchain-mcp-adapters --with langchain-anthropic \
        --with langgraph python /path/to/finos-mcp/examples/langgraph_agent.py

Why a separate environment: ``langchain-mcp-adapters`` pins the MCP SDK to 1.x (it imports
``mcp.shared.context.RequestContext``, removed in 2.x), while these servers are built on the
2.x SDK. That is not a conflict in practice, because the adapter speaks to each server as a
**stdio subprocess over the MCP wire protocol** -- the client's SDK version is independent of
the server's. It is only a conflict if you force both into one interpreter, which is exactly
what installing them into one venv would do. This mirrors the real deployment shape: your
agent app brings its own dependencies and launches the servers as processes.

Nothing here writes anywhere: every tool is read-only and the servers make no network calls.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SYSTEM = (
    "You are a financial-services governance and data-standards assistant with read-only "
    "FINOS tools (AIGF risks/controls, CDM types and validation, FDC3 intents/contexts). "
    "Answer only from tool results. Every AIGF risk or control must carry its AIR-* id; "
    "cite the aigf://, cdm:// or fdc3:// resource you relied on. Be concise."
)

QUESTIONS = [
    "Which AIGF controls mitigate prompt injection, and what do they map to in NIST SP 800-53?",
    "Describe the CDM TradeState type and tell me which fields are mandatory.",
    "I have an fdc3.instrument context for AAPL. Which intents can I raise, and which one shows a chart?",
]


async def main(questions: list[str]) -> None:
    from langchain_anthropic import ChatAnthropic
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langgraph.prebuilt import create_react_agent

    # `--directory` pins each server to the workspace venv (MCP SDK 2.x) regardless of the
    # environment this script itself runs in; `--no-sync` keeps a caller's isolated env from
    # provoking a re-resolve of the workspace.
    client = MultiServerMCPClient(
        {
            name: {
                "command": "uv",
                "args": ["run", "--directory", str(REPO), "--no-sync", f"finos-mcp-{name}"],
                "transport": "stdio",
            }
            for name in ("aigf", "cdm", "fdc3")
        }
    )
    tools = await client.get_tools()
    model = ChatAnthropic(model="claude-haiku-4-5", max_tokens=8000)
    agent = create_react_agent(model, tools, prompt=SYSTEM)
    for q in questions:
        print(f"\n=== {q}")
        result = await agent.ainvoke({"messages": [("user", q)]})
        print(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or QUESTIONS))
