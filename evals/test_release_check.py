"""Release checks must fail closed on mismatched tags and package versions."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "release_check.py"


def test_matching_release_manifest_and_lock() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]["version"]
    result = subprocess.run(
        [sys.executable, str(CHECK), "--tag", f"v{version}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert f"six manifests and uv.lock match v{version}" in result.stdout


def test_release_check_rejects_mismatched_tag() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECK), "--tag", "v0.0.0"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert result.returncode != 0
    assert "does not match package version" in result.stderr
