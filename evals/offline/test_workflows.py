"""Offline CDM/FDC3 multi-tool workflow evaluations (no external API)."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from typing import Any

import pytest
from mcp.client import Client

from finos_mcp.core import ErrorEnvelope

ROOT = Path(__file__).parent
SERVERS = ("cdm", "fdc3")


def _load_scenarios() -> list[dict[str, Any]]:
    tasks = []
    for server in SERVERS:
        data = json.loads((ROOT / f"tasks_{server}.json").read_text(encoding="utf-8"))
        tasks.extend({"server": server, **row} for row in data)
    return tasks


SCENARIOS = _load_scenarios()


def _resolve(value: Any, outputs: dict[str, Any]) -> Any:
    """Substitute actual response data via {'$from': 'step.field.0.name'}."""
    if isinstance(value, dict):
        if set(value) == {"$from"}:
            step, *parts = value["$from"].split(".")
            current = outputs[step]
            for part in parts:
                current = current[int(part)] if isinstance(current, list) else current[part]
            return current
        return {key: _resolve(part, outputs) for key, part in value.items()}
    if isinstance(value, list):
        return [_resolve(part, outputs) for part in value]
    return value


def _check(actual: Any, expected: Any, path: str = "$") -> None:
    """Partial schema checks plus list/numeric/suffix constraints."""
    if isinstance(expected, dict):
        operators = [key for key in expected if key.startswith("$")]
        if operators:
            assert len(operators) == len(expected) == 1, f"{path}: ambiguous operators"
            op = operators[0]
            target = expected[op]
            if op == "$len":
                assert isinstance(actual, list) and len(actual) == target, path
            elif op == "$min_len":
                assert isinstance(actual, list) and len(actual) >= target, path
            elif op == "$min":
                assert isinstance(actual, int | float) and actual >= target, path
            elif op == "$suffix":
                assert isinstance(actual, str) and actual.endswith(target), path
            elif op == "$contains":
                assert isinstance(actual, list) and all(x in actual for x in target), path
            elif op == "$first":
                assert isinstance(actual, list) and actual, f"{path}: empty list"
                _check(actual[0], target, path + "[0]")
            elif op == "$any":
                assert isinstance(actual, list) and actual, f"{path}: empty list"
                problems: list[str] = []
                for i, item in enumerate(actual):
                    try:
                        _check(item, target, f"{path}[{i}]")
                        return
                    except AssertionError as exc:
                        problems.append(str(exc))
                pytest.fail(f"{path}: no match for {target!r}; sample errors: {problems[:3]}")
            else:
                raise ValueError(f"unsupported operator {op}")
            return
        assert isinstance(actual, dict), f"{path}: expected an object"
        for key, part in expected.items():
            assert key in actual, f"{path}: missing {key}"
            _check(actual[key], part, f"{path}.{key}")
        return
    assert actual == expected, f"{path}: got {actual!r}, expected {expected!r}"


async def _run(task: dict[str, Any]) -> int:
    module = importlib.import_module(f"finos_mcp.{task['server']}.server")
    outputs: dict[str, Any] = {}
    # Keep the original assertion outside Client.__aexit__: anyio task-group
    # shutdown otherwise wraps the actionable error in an opaque ExceptionGroup.
    failure: Exception | None = None
    async with Client(module.create_server(), raise_exceptions=True) as client:
        try:
            available = {t.name for t in (await client.list_tools()).tools}
            for step in task["steps"]:
                name = f"{task['id']}.{step['id']}"
                if "tool" in step:
                    assert step["tool"] in available, f"{name}: unknown tool"
                    result = await client.call_tool(step["tool"], _resolve(step["args"], outputs))
                    if "expect_error" in step:
                        assert result.is_error, f"{name}: expected {step['expect_error']}"
                        error = ErrorEnvelope.parse_text(result.content[0].text)
                        assert error is not None and error.code == step["expect_error"], (
                            f"{name}: incorrect error: {result.content}"
                        )
                    else:
                        assert not result.is_error, f"{name}: {result.content}"
                        assert result.structured_content is not None, f"{name}: no structured data"
                        outputs[step["id"]] = result.structured_content
                        _check(result.structured_content, step["expect"], name)
                else:
                    uri = _resolve(step["read"], outputs)
                    assert isinstance(uri, str) and uri.startswith(f"{task['server']}://"), name
                    response = await client.read_resource(uri)
                    assert response.contents, f"{name}: empty resource"
                    content = response.contents[0].text
                    assert isinstance(content, str) and content, f"{name}: no resource text"
                    if "expect_json" in step:
                        _check(json.loads(content), step["expect_json"], name)
                    if "contains" in step:
                        assert step["contains"] in content, f"{name}: missing citation text"
                    outputs[step["id"]] = content
        except Exception as exc:
            failure = exc
    if failure is not None:
        raise failure
    return len(task["steps"])


def test_offline_scenario_dataset() -> None:
    assert len(SCENARIOS) == 16
    assert {s: sum(t["server"] == s for t in SCENARIOS) for s in SERVERS} == {
        "cdm": 8,
        "fdc3": 8,
    }
    unique: set[str] = set()
    for task in SCENARIOS:
        assert task["id"] not in unique
        unique.add(task["id"])
        assert len(task["description"]) >= 20
        assert 2 <= len(task["steps"]) <= 5
        names: set[str] = set()
        for step in task["steps"]:
            assert step["id"] not in names
            names.add(step["id"])
            assert ("tool" in step) != ("read" in step)
            if "tool" in step:
                assert isinstance(step.get("args"), dict)
                assert ("expect" in step) != ("expect_error" in step)
            else:
                assert "expect_json" in step or "contains" in step
    for server in SERVERS:
        assert (
            sum(
                any("read" in step for step in t["steps"])
                for t in SCENARIOS
                if t["server"] == server
            )
            >= 2
        )


@pytest.mark.anyio
async def test_offline_multistep_workflows() -> None:
    counts = {name: {"count": 0, "passed": 0, "steps": 0} for name in SERVERS}
    failures: list[str] = []
    for task in SCENARIOS:
        stats = counts[task["server"]]
        stats["count"] += 1
        try:
            steps = await _run(task)
        except Exception as exc:
            failures.append(f"{task['id']}: {type(exc).__name__}: {exc}")
        else:
            stats["passed"] += 1
            stats["steps"] += steps

    passed = sum(row["passed"] for row in counts.values())
    report = {
        "offline_evals": {
            "scenarios": len(SCENARIOS),
            "passed": passed,
            "failed": len(SCENARIOS) - passed,
            "success_rate": round(passed / len(SCENARIOS), 4),
            "tool_resource_steps": sum(row["steps"] for row in counts.values()),
            "by_server": counts,
            "failures": failures,
        }
    }
    Path(os.environ.get("FINOS_MCP_OFFLINE_EVALS_OUT", "offline-evals.json")).write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    assert not failures, "\n".join(failures)
