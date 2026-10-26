"""Exercise a published FINOS MCP console command over an actual stdio session.

This script is intentionally executed with Python -I from a clean, PyPI-only
virtualenv and a working directory *outside* the repository. It imports the
installed MCP SDK, not local FINOS workspace packages. No model or API key.

Usage:
  python -I scripts/verify_published_stdio.py aigf 0.3.2 /venv/bin/finos-mcp-aigf
  python -I scripts/verify_published_stdio.py aigf 0.3.2 uvx --python 3.12 finos-mcp-aigf==0.3.2
"""

from __future__ import annotations

import argparse
import asyncio
import json
from importlib.metadata import version
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

COMPONENTS = ("aigf", "cdm", "fdc3")
CASES_PATH = Path(__file__).resolve().parents[1] / "examples" / "try_it_cases.json"


def get_value(payload: Any, path: list[str | int]) -> Any:
    for part in path:
        payload = payload[part]
    return payload


async def verify(component: str, expected_version: str, command: list[str]) -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    case = cases[component]
    assert version("finos-mcp-core") == expected_version
    assert version(f"finos-mcp-{component}") == expected_version

    params = StdioServerParameters(command=command[0], args=command[1:])
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            initialized = await session.initialize()
            assert initialized.serverInfo.name, f"{component}: missing MCP server identity"
            tools = (await session.list_tools()).tools
            matches = [tool for tool in tools if tool.name == case["tool"]]
            assert len(matches) == 1, f"{component}: required tool absent from MCP tools/list"
            result = await session.call_tool(case["tool"], case["arguments"])
            assert not result.isError, f"{component}: MCP error: {result.content}"
            payload = result.structuredContent
            assert isinstance(payload, dict), f"{component}: no structured MCP output"
            actual = get_value(payload, case["expect"]["path"])
            expected = case["expect"]["equals"]
            assert actual == expected, (
                f"{component}.{case['tool']}: expected {expected!r}, got {actual!r}"
            )
            if "citation" in case:
                citation = get_value(payload, case["citation"]["path"])
                assert isinstance(citation, str) and citation.startswith(
                    f"{component}://"
                ), f"{component}: expected citable MCP source URI"
    print(
        f"PASS: PyPI finos-mcp-{component}=={expected_version}: "
        f"stdio initialize, tools/list, {case['tool']} -> {actual}",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=COMPONENTS)
    parser.add_argument("version")
    parser.add_argument("command")
    parser.add_argument("args", nargs="*")
    args = parser.parse_args()
    if not args.version.replace(".", "").isdigit() or len(args.version.split(".")) != 3:
        parser.error("expected published X.Y.Z version")
    asyncio.run(
        asyncio.wait_for(
            verify(args.component, args.version, [args.command, *args.args]),
            timeout=150,
        )
    )


if __name__ == "__main__":
    main()
