from __future__ import annotations

import json
from pathlib import Path

import pytest

from finos_mcp.core import (
    Catalog,
    Document,
    FinosToolError,
    SchemaRegistry,
    VendorIntegrityError,
    build_manifest,
    normalize_id,
    split_sections,
    verify,
)

DOCS = [
    Document(
        id="AIR-SEC-010",
        title="Prompt Injection",
        aliases=["ri-10", "10"],
        body="Adversarial instructions embedded in inputs cause the model to deviate from its task.",
        sections=split_sections(
            "## Summary\nAttackers hide instructions in documents.\n## Impact\nData exfiltration."
        ),
    ),
    Document(
        id="AIR-PREV-020",
        title="MCP Server Security Governance",
        aliases=["mi-20", "20"],
        body="Govern MCP servers: vetting, allow-listing, monitoring of tool servers used by agents.",
        sections=split_sections(
            "## Purpose\nControl which MCP servers an agent may call.\n## Guidance\nUse allow lists."
        ),
    ),
    Document(
        id="AIR-PREV-004",
        title="Prompt Injection Filtering",
        aliases=["mi-4", "4"],
        body="Filter and detect prompt injection attempts before they reach the model.",
    ),
]


def make_catalog() -> Catalog:
    return Catalog(DOCS, kind="record", citation_uri=lambda d: f"test://{d.id}")


def test_normalize_id_aligns_forms() -> None:
    assert normalize_id("AIR-SEC-010") == normalize_id("air sec 10") == normalize_id("air_sec_010")
    assert normalize_id("ri-10") == "ri10"


def test_resolve_by_id_alias_title_and_fuzzy() -> None:
    cat = make_catalog()
    assert cat.resolve("AIR-SEC-010").id == "AIR-SEC-010"
    assert cat.resolve("air-sec-10").id == "AIR-SEC-010"
    assert cat.resolve("ri-10").id == "AIR-SEC-010"
    assert cat.resolve("mcp server security governance").id == "AIR-PREV-020"
    assert cat.resolve("MCP Server Security Governence").id == "AIR-PREV-020"  # typo, fuzzy


def test_resolve_ambiguous_and_not_found() -> None:
    cat = make_catalog()
    assert cat.resolve("prompt injection").id == "AIR-SEC-010"  # exact title wins
    with pytest.raises(FinosToolError) as exc:
        cat.resolve("Prompt Inject")  # scores ~90 against two titles
    assert exc.value.envelope.code == "ambiguous_id"
    assert set(exc.value.envelope.candidates) >= {"AIR-SEC-010", "AIR-PREV-004"}
    with pytest.raises(FinosToolError) as exc2:
        cat.resolve("zzzz-unrelated")
    assert exc2.value.envelope.code == "not_found"
    assert cat.get("nope") is None


def test_search_ranks_relevant_first_and_returns_citations() -> None:
    cat = make_catalog()
    hits = cat.search("allow list MCP servers agents call", k=3)
    assert hits and hits[0].id == "AIR-PREV-020"
    assert hits[0].citation_uri == "test://AIR-PREV-020"
    assert hits[0].snippet
    assert cat.search("", k=3) == []
    only_prev = cat.search("prompt injection", k=5, predicate=lambda d: d.id.startswith("AIR-PREV"))
    assert {h.id for h in only_prev} == {"AIR-PREV-004"}


def test_split_sections_handles_fences_and_preamble() -> None:
    md = "intro\n## A\ntext\n```\n## not a heading\n```\n### B\nmore"
    secs = split_sections(md)
    assert [s.slug for s in secs] == ["preamble", "a", "b"]
    assert "## not a heading" in secs[1].body
    assert secs[2].level == 3


def _write_schemas(d: Path, dialect_uri: str, with_id: bool) -> None:
    base = {
        "$schema": dialect_uri,
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 2},
        },
        "required": ["name"],
    }
    child = {
        "$schema": dialect_uri,
        "type": "object",
        "properties": {"base": {"$ref": "base.schema.json"}, "kind": {"enum": ["a", "b"]}},
        "required": ["base"],
        "additionalProperties": False,
    }
    if with_id:
        base["$id"] = "https://example.org/schemas/next/base.schema.json"
        child["$id"] = "https://example.org/schemas/next/child.schema.json"
    (d / "base.schema.json").write_text(json.dumps(base), encoding="utf-8")
    (d / "child.schema.json").write_text(json.dumps(child), encoding="utf-8")


@pytest.mark.parametrize(
    ("dialect", "uri", "with_id"),
    [
        ("draft4", "http://json-schema.org/draft-04/schema#", False),
        ("draft2019-09", "https://json-schema.org/draft/2019-09/schema", True),
    ],
)
def test_schema_registry_resolves_sibling_refs(
    tmp_path: Path, dialect: str, uri: str, with_id: bool
) -> None:
    _write_schemas(tmp_path, uri, with_id)
    reg = SchemaRegistry.from_directory(tmp_path, dialect=dialect)  # type: ignore[arg-type]
    assert len(reg) == 2 and "child.schema.json" in reg
    good = reg.validate({"base": {"name": "x", "tags": ["a"]}, "kind": "a"}, "child.schema.json")
    assert good.valid, good.issues
    bad = reg.validate(
        {"base": {"tags": ["a", "b", "c"]}, "kind": "z", "extra": 1}, "child.schema.json"
    )
    assert not bad.valid
    kinds = {(i.json_path, i.kind) for i in bad.issues}
    assert ("$.base", "required") in kinds
    assert ("$.base.tags", "cardinality") in kinds
    assert ("$.kind", "enum") in kinds
    assert ("$", "unknown_field") in kinds
    if with_id:
        assert reg.schema("https://example.org/schemas/next/child.schema.json")["required"] == [
            "base"
        ]


def test_vendor_manifest_roundtrip_and_tamper_detection(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("alpha", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.yml").write_text("b: 1", encoding="utf-8")
    manifest = build_manifest(
        tmp_path, upstream_repo="finos/x", ref="main", commit_sha="deadbeef", license="CC-BY-4.0"
    )
    manifest.save(tmp_path)
    assert set(manifest.files) == {"a.md", "sub/b.yml"}
    loaded = verify(tmp_path)
    assert loaded.commit_sha == "deadbeef"
    (tmp_path / "a.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(VendorIntegrityError, match="changed"):
        verify(tmp_path)
    (tmp_path / "a.md").write_text("alpha", encoding="utf-8")
    (tmp_path / "c.txt").write_text("new", encoding="utf-8")
    with pytest.raises(VendorIntegrityError, match="extra"):
        verify(tmp_path)
