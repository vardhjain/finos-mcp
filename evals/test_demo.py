"""End-to-end smoke test of the low-memory, no-API-cost demo."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "examples" / "demo_session.py"


def test_demo_runs_five_real_tools_in_separate_workers(tmp_path: Path) -> None:
    env = dict(os.environ, FINOS_MCP_AUDIT_PATH=str(tmp_path / "demo-audit.jsonl"))
    result = subprocess.run(
        [sys.executable, "-u", str(DEMO), "--fast"],
        cwd=REPO,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    transcript = result.stdout
    assert transcript.count("DEMO DONE") == 1
    assert transcript.count("[read-only, rate-limited, audited]") == 5
    assert len(re.findall(r"^\$ (?:aigf|cdm|fdc3) > ", transcript, re.M)) == 5
    assert transcript.count("$ aigf > ") == 3
    assert transcript.count("$ cdm > ") == 1
    assert transcript.count("$ fdc3 > ") == 1
    assert "AIR-PREV-020" in transcript
    assert "aigf://control/AIR-PREV-020" in transcript
    assert "AIR-" in transcript
    assert "valid=False" in transcript
    assert "format=rune" in transcript
    assert "3 issue(s)" in transcript
    assert "$.after[0]" in transcript
    assert "ViewChart" in transcript
    assert "fdc3.instrument" in transcript
    assert "Traceback (most recent call last)" not in result.stderr


def test_demo_rejects_unknown_worker() -> None:
    result = subprocess.run(
        [sys.executable, str(DEMO), "--worker", "unknown"],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=15,
        check=False,
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr
