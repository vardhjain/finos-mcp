"""Release checks must fail closed on mismatched tags and package versions."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from importlib import import_module
from importlib.metadata import version as distribution_version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "release_check.py"


def test_matching_release_manifest_and_lock() -> None:
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = manifest["project"]["version"]
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


def test_running_package_versions_match_installed_distribution_metadata() -> None:
    """Server factories must announce their installed versions, not a stale constant."""
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expected = manifest["project"]["version"]
    for component in ("core", "aigf", "cdm", "fdc3"):
        module = import_module(f"finos_mcp.{component}")
        installed = distribution_version(f"finos-mcp-{component}")
        assert installed == expected
        assert module.__version__ == installed
