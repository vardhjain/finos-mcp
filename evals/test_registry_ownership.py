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


def test_directory_guide_does_not_promise_an_existing_registry_entry() -> None:
    guide = (ROOT / "docs" / "directory-listings.md").read_text(encoding="utf-8")
    assert "Publication **not verified**" in guide
    assert "the already-published v0.3.1 distributions predate" in guide
    assert "Glama" in guide
    assert "No submissions" in guide
