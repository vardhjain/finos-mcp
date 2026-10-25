"""A memory-bounded live demo using one short-lived MCP server worker at a time.

The parent imports no FINOS server; each child imports exactly one server,
executes its real MCP tool calls, streams compact JSON-rendered results, and exits
before the next server is started. This avoids the old all-servers-in-memory
CDM validation crash, with no paid models or external APIs.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.client import Client

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


SERVER_NAMES = ("aigf", "cdm", "fdc3")


async def worker(server: str) -> None:
    """Serve one demo segment, outputting JSON lines only on stdout."""
    module = importlib.import_module(f"finos_mcp.{server}.server")
    steps = [(index, step) for index, step in enumerate(STEPS) if step[1] == server]
    async with Client(module.create_server(), raise_exceptions=True) as client:
        for index, (_title, _server, tool, args, render) in steps:
            started = time.perf_counter()
            result = await client.call_tool(tool, args)
            if result.is_error:
                raise RuntimeError(f"{server}.{tool}: {result.content}")
            payload = {
                "index": index,
                "lines": render(dict(result.structured_content or {})),
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            }
            print(json.dumps(payload, ensure_ascii=False), flush=True)


async def main(*, fast: bool = False) -> None:
    """Stream each worker's live output while keeping peak memory bounded."""

    async def say(message: str, pause: float = 0.0) -> None:
        print(message, flush=True)
        # Nonblocking: an MCP worker may have its own event loop.
        await asyncio.sleep(0 if fast else pause)

    await say("starting FINOS MCP demo (isolated servers, one at a time) ...")
    await say("READY")
    await say("")
    await say("$ finos-mcp: read-only MCP servers for FINOS standards (AIGF, CDM, FDC3)", 1.0)
    for server in SERVER_NAMES:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-u",
            str(Path(__file__).resolve()),
            "--worker",
            server,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert process.stdout is not None and process.stderr is not None
        completed: set[int] = set()
        try:
            # Worker emits one line per completed tool call. We never cache
            # schema registries or model weights in the parent.
            async for raw in process.stdout:
                result = json.loads(raw.decode("utf-8"))
                index = result["index"]
                assert isinstance(index, int) and index not in completed
                title, declared, tool, args, _render = STEPS[index]
                assert declared == server, "worker returned an unexpected server"
                completed.add(index)
                await say("")
                await say(f"# {title}", 0.3)
                shown = {
                    key: ("<broken_execution.json>" if key == "object" else value)
                    for key, value in args.items()
                }
                await say(f"$ {server} > {tool} {json.dumps(shown)[:96]}", 0.2)
                for line in result["lines"]:
                    await say(str(line))
                await say("[read-only, rate-limited, audited]", 0.8)
            code = await process.wait()
            stderr = (await process.stderr.read()).decode("utf-8", errors="replace")
            if code:
                raise RuntimeError(f"{server} worker failed ({code}): {stderr[-2000:]}")
            expected = {i for i, step in enumerate(STEPS) if step[1] == server}
            if completed != expected:
                raise RuntimeError(f"{server} returned {completed}; expected {expected}")
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
        # This process is fully gone before another FINOS server is created.
    await say("")
    await say("$ every tool is read-only; nothing here writes to any external system.", 0.5)
    await say("DEMO DONE")


def cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fast", action="store_true", help="Skip pauses for CI and transcripts")
    parser.add_argument("--worker", choices=SERVER_NAMES, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        asyncio.run(worker(args.worker))
    else:
        asyncio.run(main(fast=args.fast))


if __name__ == "__main__":
    cli()
