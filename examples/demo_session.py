"""Scripted terminal demo: one process, three servers, five real tool calls.

Used by examples/demo.tape so the recording is not dominated by interpreter start-up.
Every result shown is produced live by the in-memory MCP client; nothing is canned.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

from mcp.client import Client

from finos_mcp.aigf.server import create_server as aigf_server
from finos_mcp.cdm.server import create_server as cdm_server
from finos_mcp.fdc3.server import create_server as fdc3_server

BROKEN = Path(__file__).with_name("broken_execution.json")

STEPS: list[tuple[str, str, str, dict[str, Any], int]] = [
    (
        "AIGF: resolve a control by its short id and see what it mitigates",
        "aigf",
        "get_control",
        {"id": "mi-20", "include_sections": False},
        1600,
    ),
    (
        "AIGF: reverse crosswalk, which controls cite NIST SP 800-53 SA-9?",
        "aigf",
        "find_by_external_reference",
        {"key": "sa-9"},
        1400,
    ),
    (
        "AIGF: full-text search with citable resource URIs",
        "aigf",
        "search_framework",
        {"query": "an employee pastes client data into a public chatbot", "k": 3},
        1400,
    ),
    (
        "CDM: validate a Rune-format BusinessEvent that an agent got wrong (3 defects)",
        "cdm",
        "validate_object",
        {"object": json.loads(BROKEN.read_text(encoding="utf-8"), strict=False)},
        1800,
    ),
    (
        "FDC3: which intents can I raise for an instrument, and which shows a chart?",
        "fdc3",
        "suggest_intent",
        {
            "context": {"type": "fdc3.instrument", "id": {"ticker": "AAPL"}},
            "goal": "show a price chart",
        },
        1400,
    ),
]


def say(text: str, pause: float = 0.0) -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()
    if pause:
        time.sleep(pause)


async def main() -> None:
    say("loading finos-mcp servers ...")
    servers = {"aigf": aigf_server(), "cdm": cdm_server(), "fdc3": fdc3_server()}
    clients: dict[str, Client] = {}
    for name, srv in servers.items():
        clients[name] = await Client(srv, raise_exceptions=True).__aenter__()
    say("READY", 0.5)
    say("")
    say("$ finos-mcp: typed, read-only MCP servers for FINOS standards (AIGF, CDM, FDC3)", 2.0)
    for title, server, tool, args, width in STEPS:
        say("")
        say(f"# {title}", 1.5)
        shown = {k: ("<broken_execution.json>" if k == "object" else v) for k, v in args.items()}
        say(f"$ {server} > {tool} {json.dumps(shown)}", 1.0)
        t0 = time.perf_counter()
        result = await clients[server].call_tool(tool, args)
        ms = (time.perf_counter() - t0) * 1000
        if result.is_error:
            say(result.content[0].text)  # type: ignore[union-attr]
        else:
            body = json.dumps(result.structured_content, indent=1)
            say(body[:width] + (" ..." if len(body) > width else ""))
        say(f"[{ms:.0f} ms, read-only, rate-limited, audited]", 4.0)
    say("")
    say("$ every tool is read-only; nothing here writes to any external system.", 3.0)
    say("DEMO DONE")
    for name in reversed(list(clients)):
        await clients[name].__aexit__(None, None, None)


if __name__ == "__main__":
    asyncio.run(main())
