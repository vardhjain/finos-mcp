"""Three small, real MCP tool calls: no model key, no paid APIs.

Run after `uv sync --all-packages` from the repository root:

    uv run --no-sync python examples/try_it.py aigf
    uv run --no-sync python examples/try_it.py cdm
    uv run --no-sync python examples/try_it.py fdc3

Each invocation creates exactly one in-memory server and exits.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
from pathlib import Path
from typing import Any

from mcp.client import Client

CASES_PATH = Path(__file__).with_name("try_it_cases.json")
SERVER_NAMES = ("aigf", "cdm", "fdc3")


def value_at(data: object, path: list[str | int]) -> object:
    value = data
    for part in path:
        if (isinstance(part, str) and isinstance(value, dict)) or (
            isinstance(part, int) and isinstance(value, list)
        ):
            value = value[part]
        else:
            raise ValueError(f"unexpected result shape at {part!r}")
    return value


async def run(server: str) -> int:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    case: dict[str, Any] = cases[server]
    module = importlib.import_module(f"finos_mcp.{server}.server")
    async with Client(module.create_server(), raise_exceptions=True) as client:
        result = await client.call_tool(case["tool"], case["arguments"])

    if result.is_error or result.structured_content is None:
        print(f"FAIL [{server}]: {result.content}")
        return 1
    data = result.structured_content
    expected = case["expect"]["equals"]
    actual = value_at(data, case["expect"]["path"])
    if actual != expected:
        print(f"FAIL [{server}]: expected {expected!r}, got {actual!r}")
        return 1
    print(f"PASS [{server}]: {case['tool']} returned {actual}")
    if "citation" in case:
        print(f"Source: {value_at(data, case['citation']['path'])}")
    print("This was a real, local MCP tool call; no LLM was used.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Try a real read-only FINOS MCP tool call")
    parser.add_argument("server", choices=SERVER_NAMES)
    args = parser.parse_args()
    return asyncio.run(run(args.server))


if __name__ == "__main__":
    raise SystemExit(main())
