"""Scripted terminal demo: one process, three servers, five real tool calls.

Used by examples/demo.tape so the recording is not dominated by interpreter start-up,
and by `docs/demo.md`, which is this script's captured output. Every line shown is
produced live by the in-memory MCP client; nothing is canned.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.client import Client

from finos_mcp.aigf.server import create_server as aigf_server
from finos_mcp.cdm.server import create_server as cdm_server
from finos_mcp.fdc3.server import create_server as fdc3_server

# Library debug chatter (bm25s index building, httpx) goes to stderr and would appear in the
# recording beside the demo output. The audit log is redirected with FINOS_MCP_AUDIT_PATH by
# the tape for the same reason. Both emit at runtime, so disabling here is early enough.
logging.disable(logging.INFO)

BROKEN = Path(__file__).with_name("broken_execution.json")


def show_control(r: dict[str, Any]) -> list[str]:
    return [
        f"{r['id']}  {r['title']}  [{r['type_label']}, {r['status']}]",
        f"mitigates        {', '.join(r['mitigates'])}",
        f"related controls {', '.join(r['related_controls'])}",
        f"crosswalks to    {len(r['references'])} references across "
        f"{len({x['framework'] for x in r['references']})} frameworks",
        f"cite             {r['citation_uri']}",
    ]


def show_crosswalk(r: dict[str, Any]) -> list[str]:
    out = [f"{len(r['matches'])} AIGF records cite this reference:"]
    out += [f"  {m['kind']:7} {m['id']}  {m['title']}" for m in r["matches"][:4]]
    return out


def show_search(r: dict[str, Any]) -> list[str]:
    return [f"  {h['id']}  {h['title']}\n      {h['citation_uri']}" for h in r["hits"]]


def show_validation(r: dict[str, Any]) -> list[str]:
    out = [
        f"valid={r['valid']}   format={r['format_detected']}   type={r['type']}",
        f"validator: {r['validator']}",
        f"{len(r['issues'])} issue(s):",
    ]
    out += [f"  [{i['kind']:11}] {i['json_path']}\n      {i['message'][:96]}" for i in r["issues"]]
    return out


def show_intents(r: dict[str, Any]) -> list[str]:
    out = [f"context {r['context_type']} (detected by {r['detected_by']}); ranked intents:"]
    out += [f"  {s['score']:.2f}  {s['name']:18} {s['reason'][:58]}" for s in r["suggestions"][:5]]
    return out


# (title, server, tool, arguments, renderer) -- renderers keep each step to a handful of
# meaningful lines instead of dumping raw JSON, which is both easier to read and far less
# output for a terminal recorder to keep up with.
STEPS: list[tuple[str, str, str, dict[str, Any], Callable[[dict[str, Any]], list[str]]]] = [
    (
        "AIGF: resolve a control by its short id and see what it mitigates",
        "aigf",
        "get_control",
        {"id": "mi-20", "include_sections": False},
        show_control,
    ),
    (
        "AIGF: reverse crosswalk, which records cite NIST SP 800-53 SA-9?",
        "aigf",
        "find_by_external_reference",
        {"key": "sa-9"},
        show_crosswalk,
    ),
    (
        "AIGF: search in plain language, every hit is citable",
        "aigf",
        "search_framework",
        {"query": "an employee pastes client data into a public chatbot", "k": 3},
        show_search,
    ),
    (
        "CDM: validate a Rune BusinessEvent an agent got wrong (3 planted defects)",
        "cdm",
        "validate_object",
        {"object": json.loads(BROKEN.read_text(encoding="utf-8"), strict=False)},
        show_validation,
    ),
    (
        "FDC3: which intents can I raise for an instrument, and which shows a chart?",
        "fdc3",
        "suggest_intent",
        {
            "context": {"type": "fdc3.instrument", "id": {"ticker": "AAPL"}},
            "goal": "show a price chart",
        },
        show_intents,
    ),
]


async def say(text: str, pause: float = 0.0) -> None:
    """Print one line, then yield.

    `asyncio.sleep`, never `time.sleep`: an MCP `Client` runs a message-dispatch
    task on this loop, and blocking it for seconds at a time while a session is
    open starves that task and wedges the next `call_tool`.
    """
    sys.stdout.write(text + "\n")
    sys.stdout.flush()
    await asyncio.sleep(pause if pause else 0)


async def main() -> None:
    await say("loading finos-mcp servers ...")
    servers = {"aigf": aigf_server(), "cdm": cdm_server(), "fdc3": fdc3_server()}
    clients: dict[str, Client] = {}
    for name, srv in servers.items():
        clients[name] = await Client(srv, raise_exceptions=True).__aenter__()
    await say("READY", 0.5)
    await say("")
    await say("$ finos-mcp: read-only MCP servers for FINOS standards (AIGF, CDM, FDC3)", 1.5)
    for title, server, tool, args, render in STEPS:
        await say("")
        await say(f"# {title}", 1.2)
        shown = {k: ("<broken_execution.json>" if k == "object" else v) for k, v in args.items()}
        await say(f"$ {server} > {tool} {json.dumps(shown)[:96]}", 0.8)
        t0 = time.perf_counter()
        result = await clients[server].call_tool(tool, args)
        ms = (time.perf_counter() - t0) * 1000
        if result.is_error:
            await say(str(result.content[0].text))  # type: ignore[union-attr]
        else:
            for line in render(dict(result.structured_content or {})):
                await say(line)
        await say(f"[{ms:.0f} ms, read-only, rate-limited, audited]", 2.5)
    await say("")
    await say("$ every tool is read-only; nothing here writes to any external system.", 2.0)
    await say("DEMO DONE")
    for name in reversed(list(clients)):
        await clients[name].__aexit__(None, None, None)


if __name__ == "__main__":
    asyncio.run(main())
