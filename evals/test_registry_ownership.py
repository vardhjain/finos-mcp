"""Verify official MCP Registry ownership markers are consistent with PyPI metadata.

These checks do not publish packages or call a directory.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO_OWNER = "vardhjain"
COMPONENTS = ("aigf", "cdm", "fdc3")


@pytest.mark.parametrize("component", COMPONENTS)
def test_pypi_readme_contains_exact_registry_ownership_marker(component: str) -> None:
    folder = ROOT / "servers" / component
    manifest = tomllib.loads((folder / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["project"]["name"] == f"finos-mcp-{component}"
    assert manifest["project"]["readme"] == "README.md"
    assert manifest["project"]["scripts"][f"finos-mcp-{component}"]
    readme = (folder / "README.md").read_text(encoding="utf-8")
    expected = f"<!-- mcp-name: io.github.{REPO_OWNER}/finos-mcp-{component} -->"
    assert readme.count(expected) == 1
    assert readme.count("mcp-name:") == 1
    assert "Not affiliated with or endorsed by FINOS" in readme


def test_directory_guide_records_verified_public_registry_entries() -> None:
    guide = (ROOT / "docs" / "directory-listings.md").read_text(encoding="utf-8")
    assert "All three v0.3.2 servers published and independently verified active" in guide
    for component in COMPONENTS:
        assert f"io.github.vardhjain/finos-mcp-{component}" in guide
        assert f"finos-mcp-{component}==0.3.2" in guide
        assert f"io.github.vardhjain%2Ffinos-mcp-{component}/versions/0.3.2" in guide
    assert "40389712353" in guide  # successful owner-triggered submission
    assert "40390604767" in guide  # independent public API verification
    assert "not FINOS endorsement" in guide
    assert "Do not rerun the v0.3.2 publication batch" in guide
    assert "Glama" in guide
