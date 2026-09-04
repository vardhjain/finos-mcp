"""Latency benchmark: p50/p95/p99 per tool through the in-memory MCP client.

Runs each representative call N times (default 200), asserts p95 budgets, and
writes ``perf.json`` (``{"latency_ms_p95": {"aigf.search_framework": 3.1, ...}}``)
for the metrics collector.

    uv run python evals/perf/bench.py [--n 200] [--out perf.json]
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from mcp.client import Client

from finos_mcp.core import RateLimit, runtime_for

# Representative calls per server: (tool, arguments, p95 budget in ms).
CASES: dict[str, list[tuple[str, dict[str, Any], float]]] = {
    "aigf": [
        ("get_control", {"id": "AIR-PREV-020", "include_sections": False}, 10.0),
        ("get_risk", {"id": "ri-10"}, 10.0),
        ("search_framework", {"query": "prompt injection in agent tool calls", "k": 5}, 25.0),
        ("map_risks_to_controls", {"risk_ids": ["ri-10", "ri-26", "ri-1"]}, 10.0),
        ("find_by_external_reference", {"key": "sa-9"}, 10.0),
        ("list_risks", {"page_size": 50}, 10.0),
    ],
    "cdm": [
        ("describe_type", {"name": "TradeState"}, 5.0),
        ("list_types", {"page_size": 50}, 10.0),
        ("search_types", {"query": "interest rate payout", "k": 5}, 25.0),
    ],
    "fdc3": [
        ("get_context_schema", {"type": "fdc3.instrument"}, 5.0),
        (
            "validate_context",
            {"context": {"type": "fdc3.instrument", "id": {"ticker": "AAPL"}}},
            10.0,
        ),
        (
            "suggest_intent",
            {"context": {"type": "fdc3.instrument", "id": {"ticker": "AAPL"}}},
            10.0,
        ),
        ("list_intents", {}, 10.0),
    ],
}


def percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    ordered = sorted(data)
    idx = min(len(ordered) - 1, max(0, round((p / 100.0) * (len(ordered) - 1))))
    return ordered[idx]


async def bench_server(name: str, n: int) -> dict[str, dict[str, float]]:
    try:
        module = importlib.import_module(f"finos_mcp.{name}.server")
    except ImportError:
        return {}
    factory = getattr(module, "create_server", None)
    if factory is None:
        return {}
    out: dict[str, dict[str, float]] = {}
    server = factory()
    # The benchmark measures tool latency (middleware included), not the rate policy:
    # lift the per-tool limits on this in-process instance only.
    rt = runtime_for(server)
    rt.policy.default_limit = RateLimit(calls=10_000_000, window_s=1.0, burst=10_000_000)
    rt.policy.per_tool.clear()
    async with Client(server, raise_exceptions=True) as client:
        available = {t.name for t in (await client.list_tools()).tools}
        for tool, args, budget in CASES.get(name, []):
            if tool not in available:
                continue
            # warm-up
            for _ in range(5):
                await client.call_tool(tool, args)
            samples: list[float] = []
            for _ in range(n):
                t0 = time.perf_counter()
                result = await client.call_tool(tool, args)
                samples.append((time.perf_counter() - t0) * 1000)
                assert result.is_error is False, (name, tool, result.content)
            out[f"{name}.{tool}"] = {
                "p50": round(percentile(samples, 50), 3),
                "p95": round(percentile(samples, 95), 3),
                "p99": round(percentile(samples, 99), 3),
                "mean": round(statistics.fmean(samples), 3),
                "budget_p95": budget,
                "n": n,
            }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", type=Path, default=Path("perf.json"))
    ap.add_argument(
        "--strict", action="store_true", help="exit non-zero when a p95 budget is exceeded"
    )
    args = ap.parse_args(argv)
    # Keep per-call audit lines out of the benchmark's own output unless a path was chosen.
    # Servers are created lazily inside bench_server, so this runs before any audit log opens.
    os.environ.setdefault(
        "FINOS_MCP_AUDIT_PATH", str(Path(tempfile.gettempdir()) / "finos-mcp-bench-audit.jsonl")
    )
    results: dict[str, dict[str, float]] = {}
    for server in CASES:
        results.update(asyncio.run(bench_server(server, args.n)))
    over = {k: v for k, v in results.items() if v["p95"] > v["budget_p95"]}
    sys.stdout.write(f"{'tool':40} {'p50':>8} {'p95':>8} {'p99':>8} {'budget':>8}\n")
    for k, v in sorted(results.items()):
        flag = "  OVER" if k in over else ""
        sys.stdout.write(
            f"{k:40} {v['p50']:8.2f} {v['p95']:8.2f} {v['p99']:8.2f} {v['budget_p95']:8.1f}{flag}\n"
        )
    args.out.write_text(
        json.dumps(
            {
                "latency_ms_p95": {k: v["p95"] for k, v in results.items()},
                "latency_detail": results,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if over and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
