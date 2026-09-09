"""Tier C: Claude answers AIGF questions through the real server and must cite valid ids.

Runs only when ``ANTHROPIC_API_KEY`` (or an ``ant auth`` profile) is available and
``anthropic`` is installed; skipped otherwise.  Writes ``agent.json`` (or the path in
``FINOS_MCP_AGENT_OUT``) for the metrics collector.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest

from finos_mcp.aigf.server import create_server, state

from .harness import model_from_env, run_suite

TASKS = Path(__file__).parent / "tasks_aigf.jsonl"
# Citing an id that is not in the catalog is a correctness failure with zero tolerance: the
# agent had tools to look every id up, so inventing one is never acceptable. Whether it cites
# any id at all is a separate, softer instruction-following measure, since a model may answer
# correctly in prose and omit the identifier.
MAX_HALLUCINATED_ID_RATE = 0.0
MIN_CITED_ANY_RATE = 0.90
MIN_MUST_CITE_RATE = 0.80
MIN_TOOL_CORRECTNESS = 0.80


def _tasks() -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _known_ids() -> set[str]:
    fw = state().framework
    return set(fw.risks) | set(fw.controls)


def test_task_file_is_well_formed() -> None:
    tasks = _tasks()
    known = _known_ids()
    assert len(tasks) == 20
    assert len({t["id"] for t in tasks}) == 20
    for t in tasks:
        assert t["must_cite"] and set(t["must_cite"]) <= known, (
            t["id"],
            set(t["must_cite"]) - known,
        )
        assert t["must_call"]


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"),
    reason="no Claude API credentials; tier C runs in the llm-evals workflow",
)
def test_agent_cites_valid_controls() -> None:
    pytest.importorskip("anthropic")
    tasks = _tasks()
    server = create_server()
    runs, metrics = asyncio.run(
        run_suite(
            server,
            tasks,
            _known_ids(),
            model=model_from_env(),
            use_judge=os.environ.get("EVAL_JUDGE") == "1",
        )
    )
    out = Path(os.environ.get("FINOS_MCP_AGENT_OUT", "agent.json"))
    out.write_text(
        json.dumps({"agent": metrics, "agent_runs": [r.to_json() for r in runs]}, indent=2),
        encoding="utf-8",
    )
    failures = [r.task_id for r in runs if r.error]
    assert metrics["refusals"] == 0, [r.to_json() for r in runs if r.error == "refusal"]
    assert metrics["hallucinated_id_rate"] <= MAX_HALLUCINATED_ID_RATE, (
        f"cited ids absent from the catalog: {metrics['hallucinated_ids']}"
    )
    assert metrics["cited_any_rate"] >= MIN_CITED_ANY_RATE, (
        f"tasks whose answer cited no AIR-* id: {metrics['no_citation_tasks']}; {metrics}"
    )
    assert metrics["must_cite_rate"] >= MIN_MUST_CITE_RATE, metrics
    assert metrics["tool_correctness"] >= MIN_TOOL_CORRECTNESS, metrics
    assert not failures, failures
