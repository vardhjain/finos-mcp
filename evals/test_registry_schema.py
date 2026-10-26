"""Validate all MCP Registry drafts against a pinned upstream Draft-07 schema.

The upstream schema snapshot is data, never fetched over the network during
CI, and is distinct from the final mcp-publisher semantic/ownership checks.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = ROOT / "registry" / "schema" / "upstream-draft.schema.json"
COMPONENTS = ("aigf", "cdm", "fdc3")
UPSTREAM_SHA = "e47b29ec6091a4b05969d9f755a024529ee2b5b3"


def schema_validator() -> jsonschema.Draft7Validator:
    upstream_schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert upstream_schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert upstream_schema["$ref"] == "#/definitions/ServerDetail"
    jsonschema.Draft7Validator.check_schema(upstream_schema)
    return jsonschema.Draft7Validator(upstream_schema, format_checker=jsonschema.FormatChecker())


@pytest.mark.parametrize("component", COMPONENTS)
def test_registry_manifest_validates_against_pinned_upstream_schema(component: str) -> None:
    manifest_path = ROOT / "registry" / component / "server.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = list(schema_validator().iter_errors(manifest))
    formatted = [
        f"{'.'.join(map(str, issue.absolute_path)) or '
    assert not formatted, f"{component} registry schema violations: {formatted}"


@pytest.mark.parametrize(
    ("bad_field", "bad_value"),
    [
        ("description", "x" * 101),
        ("name", "not-a-valid-registry-namespace"),
        ("packages", [{"registryType": "pypi", "identifier": "x", "transport": {}}]),
    ],
)
def test_registry_schema_detects_invalid_metadata(bad_field: str, bad_value: object) -> None:
    original = json.loads((ROOT / "registry" / "aigf" / "server.json").read_text(encoding="utf-8"))
    broken = copy.deepcopy(original)
    broken[bad_field] = bad_value
    assert not schema_validator().is_valid(broken)


def test_schema_snapshot_pin_is_documented() -> None:
    readme = (ROOT / "registry" / "README.md").read_text(encoding="utf-8")
    assert UPSTREAM_SHA in readme
    assert "not proof that the manifests pass the Registry's" in readme
    assert "mcp-publisher validate" in readme
}: {issue.message}" for issue in errors
    ]
    assert not formatted, f"{component} registry schema violations: {formatted}"


@pytest.mark.parametrize(
    ("bad_field", "bad_value"),
    [
        ("description", "x" * 101),
        ("name", "not-a-valid-registry-namespace"),
        ("packages", [{"registryType": "pypi", "identifier": "x", "transport": {}}]),
    ],
)
def test_registry_schema_detects_invalid_metadata(
    bad_field: str, bad_value: object
) -> None:
    original = json.loads(
        (ROOT / "registry" / "aigf" / "server.json").read_text(encoding="utf-8")
    )
    broken = copy.deepcopy(original)
    broken[bad_field] = bad_value
    assert not schema_validator().is_valid(broken)


def test_schema_snapshot_pin_is_documented() -> None:
    readme = (ROOT / "registry" / "README.md").read_text(encoding="utf-8")
    assert UPSTREAM_SHA in readme
    assert "not proof that the manifests pass the Registry's" in readme
    assert "mcp-publisher validate" in readme
