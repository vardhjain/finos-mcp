"""Golden tests: every JSON case under evals/golden/<server>/ is one tool call.

Case format::

    {"tool": "get_control", "args": {"id": "mi-20"},
     "expect": {"id": "AIR-PREV-020", "mitigates": {"$contains": ["AIR-SEC-026"]}}}
    {"tool": "get_risk", "args": {"id": "nope"}, "expect_error": "not_found"}

``expect`` is matched partially: dict keys present in ``expect`` must match; lists
match exactly unless wrapped in ``{"$contains": [...]}``, ``{"$len": n}``,
``{"$min_len": n}``, ``{"$first": value}`` or ``{"$any": value}``; scalars must be equal.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from mcp.client import Client

from finos_mcp.core import ErrorEnvelope

GOLDEN_DIR = Path(__file__).parent / "golden"


def _cases() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for server_dir in sorted(p for p in GOLDEN_DIR.iterdir() if p.is_dir()):
        for case in sorted(server_dir.glob("*.json")):
            out.append((server_dir.name, case))
    return out


def matches(expected: Any, actual: Any, path: str = "$") -> list[str]:
    problems: list[str] = []
    if isinstance(expected, dict) and any(k.startswith("$") for k in expected):
        if "$contains" in expected:
            missing = [x for x in expected["$contains"] if x not in (actual or [])]
            if missing:
                problems.append(f"{path}: missing {missing!r} in {actual!r}")
        if "$len" in expected and len(actual or []) != expected["$len"]:
            problems.append(f"{path}: len {len(actual or [])} != {expected['$len']}")
        if "$min_len" in expected and len(actual or []) < expected["$min_len"]:
            problems.append(f"{path}: len {len(actual or [])} < {expected['$min_len']}")
        if "$first" in expected:
            first = (actual or [None])[0]
            problems += matches(expected["$first"], first, f"{path}[0]")
        if "$any" in expected:
            items = actual or []
            if not any(not matches(expected["$any"], item, path) for item in items):
                problems.append(f"{path}: no element matches {expected['$any']!r}")
        return problems
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected object, got {type(actual).__name__}"]
        for key, value in expected.items():
            if key not in actual:
                problems.append(f"{path}.{key}: missing")
            else:
                problems += matches(value, actual[key], f"{path}.{key}")
        return problems
    if isinstance(expected, list):
        if actual != expected:
            problems.append(f"{path}: {actual!r} != {expected!r}")
        return problems
    if actual != expected:
        problems.append(f"{path}: {actual!r} != {expected!r}")
    return problems


_SERVERS: dict[str, Any] = {}


def _server(name: str) -> Any:
    if name not in _SERVERS:
        module = importlib.import_module(f"finos_mcp.{name}.server")
        _SERVERS[name] = module.create_server()
    return _SERVERS[name]


@pytest.fixture
async def client_for() -> AsyncIterator[Any]:
    clients: dict[str, Client] = {}
    stack: list[Any] = []

    async def get(name: str) -> Client:
        if name not in clients:
            cm = Client(_server(name), raise_exceptions=True)
            clients[name] = await cm.__aenter__()
            stack.append(cm)
        return clients[name]

    yield get
    for cm in reversed(stack):
        await cm.__aexit__(None, None, None)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("server", "case_path"), _cases(), ids=lambda p: p.name if isinstance(p, Path) else p
)
async def test_golden(server: str, case_path: Path, client_for: Any) -> None:
    case = json.loads(case_path.read_text(encoding="utf-8"))
    client = await client_for(server)
    result = await client.call_tool(case["tool"], case.get("args", {}))
    if "expect_error" in case:
        assert result.is_error is True, f"{case_path.name}: expected error {case['expect_error']}"
        env = ErrorEnvelope.parse_text(result.content[0].text)  # type: ignore[union-attr]
        assert env is not None and env.code == case["expect_error"], result.content[0].text  # type: ignore[union-attr]
        return
    assert result.is_error is False, f"{case_path.name}: {result.content}"
    problems = matches(case["expect"], result.structured_content)
    assert not problems, f"{case_path.name}:\n  " + "\n  ".join(problems)
