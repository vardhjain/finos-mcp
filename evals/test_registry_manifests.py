"""Offline correctness checks for draft official MCP Registry metadata."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ("aigf", "cdm", "fdc3")
SCHEMA = "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json"


@pytest.mark.parametrize("component", COMPONENTS)
def test_registry_draft_matches_pypi_package(component: str) -> None:
    package_path = ROOT / "servers" / component
    project = tomllib.loads(
        (package_path / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    workspace_version = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    draft = json.loads(
        (ROOT / "registry" / component / "server.json").read_text(encoding="utf-8")
    )
    package = f"finos-mcp-{component}"
    registered_name = f"io.github.vardhjain/{package}"
    assert project["name"] == package
    assert project["version"] == workspace_version
    assert package in project["scripts"]
    assert draft["$schema"] == SCHEMA
    assert draft["name"] == registered_name
    assert draft["version"] == workspace_version
    assert 0 < len(draft["description"]) <= 100
    assert "Independent project" in draft["description"]
    assert draft["repository"] == {
        "url": "https://github.com/vardhjain/finos-mcp",
        "source": "github",
    }
    assert draft["websiteUrl"] == "https://vardhjain.github.io/finos-mcp/"
    assert draft["packages"] == [
        {
            "registryType": "pypi",
            "registryBaseUrl": "https://pypi.org",
            "identifier": package,
            "version": workspace_version,
            "runtimeHint": "uvx",
            "transport": {"type": "stdio"},
        }
    ]
    assert "remotes" not in draft
    assert set(draft) == {
        "$schema", "name", "title", "description", "websiteUrl",
        "repository", "version", "packages",
    }
    readme = (package_path / "README.md").read_text(encoding="utf-8")
    assert f"<!-- mcp-name: {registered_name} -->" in readme


def test_three_distinct_drafts_not_auto_published() -> None:
    found = sorted(
        path.relative_to(ROOT / "registry").as_posix()
        for path in (ROOT / "registry").glob("*/server.json")
    )
    assert found == [f"{component}/server.json" for component in COMPONENTS]
    guide = (ROOT / "registry" / "README.md").read_text(encoding="utf-8")
    assert "Do not run `mcp-publisher publish`" in guide
    assert "public PyPI" in guide
    assert "0.3.1" in guide
