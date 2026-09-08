"""LangGraph agent over the three finos-mcp servers.

    uv sync --all-packages --extra llm
    export ANTHROPIC_API_KEY=...
    uv run python examples/langgraph_agent.py "Which AIGF controls mitigate prompt injection?"

Each server runs as a stdio subprocess; ``langchain-mcp-adapters`` turns their tools into
LangChain tools, and a ReAct agent on Claude answers with cited ids. Nothing here writes
anywhere: every tool is read-only and the servers make no network calls.
"""

from __future__ import annotations

import asyncio
import sys

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

    client = MultiServerMCPClient(
        {
            name: {"command": "uv", "args": ["run", f"finos-mcp-{name}"], "transport": "stdio"}
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
