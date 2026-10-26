"""Validate the three draft MCP Registry manifests against a pinned upstream schema.

Tests run fully offline and do not substitute for the official publisher CLI.
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
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
    assert schema["$ref"] == "#/definitions/ServerDetail"
    jsonschema.Draft7Validator.check_schema(schema)
    return jsonschema.Draft7Validator(schema, format_checker=jsonschema.FormatChecker())


@pytest.mark.parametrize("component", COMPONENTS)
def test_registry_manifest_validates_against_pinned_upstream_schema(component: str) -> None:
    manifest = json.loads(
        (ROOT / "registry" / component / "server.json").read_text(encoding="utf-8")
    )
    problems = list(schema_validator().iter_errors(manifest))
    assert not problems, [str(problem) for problem in problems]


@pytest.mark.parametrize("bad_case", ("overlong_description", "invalid_name", "missing_stdio_type"))
def test_registry_schema_rejects_malformed_metadata(bad_case: str) -> None:
    manifest = json.loads((ROOT / "registry" / "aigf" / "server.json").read_text(encoding="utf-8"))
    broken = copy.deepcopy(manifest)
    if bad_case == "overlong_description":
        broken["description"] = "x" * 101
    elif bad_case == "invalid_name":
        broken["name"] = "not-a-valid-namespace"
    else:
        del broken["packages"][0]["transport"]["type"]
    assert not schema_validator().is_valid(broken)


def test_upstream_pin_and_release_blocker_are_documented() -> None:
    readme = (ROOT / "registry" / "README.md").read_text(encoding="utf-8")
    assert UPSTREAM_SHA in readme
    assert "not proof that the manifests pass the Registry's" in readme
    assert "Do not run" in readme
    assert "mcp-publisher validate" in readme
