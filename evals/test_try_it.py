"""Proof that the three public 'try it' recipes call real MCP tools.

Each subprocess starts only one server to stay within CI memory limits.
No remote model or paid API is used.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "examples" / "try_it_cases.json"
SCRIPT = ROOT / "examples" / "try_it.py"


@pytest.mark.parametrize("server", ("aigf", "cdm", "fdc3"))
def test_try_it_calls_real_tool(server: str, tmp_path: Path) -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    assert set(cases) == {"aigf", "cdm", "fdc3"}
    env = dict(os.environ, FINOS_MCP_AUDIT_PATH=str(tmp_path / "demo-audit.jsonl"))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), server],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr[-1500:]
    assert f"PASS [{server}]" in result.stdout
    assert str(cases[server]["expect"]["equals"]) in result.stdout
    assert "real, local MCP tool call" in result.stdout


def test_recipes_are_linked_from_public_docs() -> None:
    guide = (ROOT / "docs" / "use-cases.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/use-cases.md" in readme
    for server in ("aigf", "cdm", "fdc3"):
        assert f"python examples/try_it.py {server}" in guide
