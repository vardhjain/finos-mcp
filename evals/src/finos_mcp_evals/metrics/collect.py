"""Collect resume-facing metrics into metrics.json and a GitHub job summary.

Sources:
* each server's ``server_info`` tool, called through the in-memory MCP client
  (exposure counts, tools, resources);
* a pytest junit.xml (test counts) and coverage.xml (line coverage);
* optional JSON side files written by the retrieval, agent and perf evals
  (``--extra path.json`` may repeat; each is merged under its top-level keys).

Usage:
    uv run python -m finos_mcp_evals.metrics.collect --junit junit.xml \
        --coverage coverage.xml --out metrics.json [--extra retrieval.json ...]
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp.client import Client

SERVERS = ("aigf", "cdm", "fdc3")


def _git_sha() -> str | None:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


async def _server_info(server: str) -> dict[str, Any] | None:
    try:
        module = importlib.import_module(f"finos_mcp.{server}.server")
    except ImportError:
        return None
    factory = getattr(module, "create_server", None)
    if factory is None:
        return None
    async with Client(factory(), raise_exceptions=True) as client:
        result = await client.call_tool("server_info", {})
        tools = (await client.list_tools()).tools
        templates = (await client.list_resource_templates()).resource_templates
        resources = (await client.list_resources()).resources
        info = dict(result.structured_content or {})
        info["tool_count"] = len(tools)
        info["resource_count"] = len(templates) + len(resources)
        return info


def exposure() -> tuple[dict[str, int], dict[str, Any]]:
    counts: dict[str, int] = {}
    details: dict[str, Any] = {}
    tools_total = resources_total = 0
    for server in SERVERS:
        info = asyncio.run(_server_info(server))
        if info is None:
            continue
        for key, value in info.get("counts", {}).items():
            counts[f"{server}.{key}"] = int(value)
        tools_total += int(info["tool_count"])
        resources_total += int(info["resource_count"])
        details[server] = {
            "version": info.get("version"),
            "standard_version": info.get("standard_version"),
            "upstream_ref": info.get("upstream_ref"),
            "upstream_commit": info.get("upstream_commit"),
            "tools": info.get("tools", []),
            "tool_count": info["tool_count"],
            "resource_count": info["resource_count"],
        }
    counts["tools_total"] = tools_total
    counts["resources_total"] = resources_total
    return counts, details


def tests_from_junit(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = failures = errors = skipped = 0
    for s in suites:
        total += int(s.get("tests", 0))
        failures += int(s.get("failures", 0))
        errors += int(s.get("errors", 0))
        skipped += int(s.get("skipped", 0))
    return {
        "count": total,
        "passed": total - failures - errors - skipped,
        "failed": failures + errors,
        "skipped": skipped,
    }


def coverage_from_xml(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    root = ET.parse(path).getroot()
    rate = float(root.get("line-rate", 0.0))
    return {"coverage_pct": round(rate * 100, 2)}


def render_summary(metrics: dict[str, Any]) -> str:
    lines = ["## finos-mcp metrics", "", "| Metric | Value |", "|---|---|"]
    for k, v in sorted(metrics.get("exposure", {}).items()):
        lines.append(f"| {k} | {v} |")
    t = metrics.get("tests", {})
    if t:
        lines.append(f"| tests | {t.get('passed', 0)}/{t.get('count', 0)} passed |")
        if "coverage_pct" in t:
            lines.append(f"| coverage | {t['coverage_pct']}% |")
    for section in ("retrieval", "agent"):
        for k, v in sorted(metrics.get(section, {}).items()):
            lines.append(f"| {section}.{k} | {v} |")
    for k, v in sorted(metrics.get("latency_ms_p95", {}).items()):
        lines.append(f"| p95 {k} | {v} ms |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--junit", type=Path)
    ap.add_argument("--coverage", type=Path)
    ap.add_argument("--extra", type=Path, action="append", default=[])
    ap.add_argument("--out", type=Path, default=Path("metrics.json"))
    args = ap.parse_args(argv)

    counts, details = exposure()
    metrics: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": _git_sha(),
        "exposure": counts,
        "servers": details,
        "tests": {**tests_from_junit(args.junit), **coverage_from_xml(args.coverage)},
        "retrieval": {},
        "agent": {},
        "latency_ms_p95": {},
    }
    for extra in args.extra:
        if extra.exists():
            data = json.loads(extra.read_text(encoding="utf-8"))
            for key, value in data.items():
                if isinstance(value, dict) and isinstance(metrics.get(key), dict):
                    metrics[key].update(value)
                else:
                    metrics[key] = value
    args.out.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = render_summary(metrics)
    sys.stdout.write(summary)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as fh:
            fh.write(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
