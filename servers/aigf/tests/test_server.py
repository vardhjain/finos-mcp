"""AIGF server tests through the real in-memory MCP client."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from mcp.client import Client
from mcp.shared.exceptions import MCPError

from finos_mcp.aigf.server import create_server, state
from finos_mcp.core import ErrorEnvelope

EXPECTED_TOOLS = {
    "list_risks",
    "get_risk",
    "list_controls",
    "get_control",
    "map_risks_to_controls",
    "map_control_to_external",
    "search_framework",
    "list_reference_frameworks",
    "find_by_external_reference",
    "server_info",
}


@pytest.mark.anyio
async def test_find_by_external_reference(client: Client) -> None:
    hits = _structured(await client.call_tool("find_by_external_reference", {"key": "SA-9"}))
    assert hits["matches"], "sa-9 is cited by AIR-PREV-020 among others"
    assert "AIR-PREV-020" in {m["id"] for m in hits["matches"]}
    assert all(m["framework"] == "nist-sp-800-53r5" for m in hits["matches"])
    scoped = _structured(
        await client.call_tool(
            "find_by_external_reference", {"key": "llm01-2025", "framework": "owasp-llm"}
        )
    )
    assert "AIR-SEC-010" in {m["id"] for m in scoped["matches"]}
    none = _structured(await client.call_tool("find_by_external_reference", {"key": "zz-999"}))
    assert none["matches"] == []
    env = _error(
        await client.call_tool("find_by_external_reference", {"key": "sa-9", "framework": "nope"})
    )
    assert env.code == "not_found"


@pytest.fixture(scope="module")
def server() -> Any:
    return create_server()


@pytest.fixture
async def client(server: Any) -> AsyncIterator[Client]:
    async with Client(server, raise_exceptions=True) as c:
        yield c


def _structured(result: Any) -> dict[str, Any]:
    assert result.is_error is False, result.content
    assert result.structured_content is not None
    return dict(result.structured_content)


def _error(result: Any) -> ErrorEnvelope:
    assert result.is_error is True
    env = ErrorEnvelope.parse_text(result.content[0].text)
    assert env is not None, result.content[0].text
    return env


@pytest.mark.anyio
async def test_tool_surface_is_typed_and_read_only(client: Client) -> None:
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == EXPECTED_TOOLS
    for t in tools:
        assert t.annotations is not None and t.annotations.read_only_hint is True
        assert t.output_schema is not None, t.name
        assert t.description, t.name


@pytest.mark.anyio
async def test_list_risks_filters_and_paginates(client: Client) -> None:
    page = _structured(await client.call_tool("list_risks", {"page_size": 10}))
    assert page["total"] == 23 and len(page["items"]) == 10 and page["page"] == 1
    sec = _structured(await client.call_tool("list_risks", {"type": "SEC", "page_size": 50}))
    assert sec["total"] > 0 and all(i["type"] == "SEC" for i in sec["items"])
    assert all(i["id"].startswith("AIR-SEC-") for i in sec["items"])
    bad = _error(await client.call_tool("list_risks", {"page_size": 500}))
    assert bad.code == "invalid_input"


@pytest.mark.anyio
async def test_get_risk_accepts_every_id_form(client: Client) -> None:
    for form in ("AIR-SEC-010", "air-sec-10", "ri-10", "10", "Prompt Injection"):
        risk = _structured(await client.call_tool("get_risk", {"id": form}))
        assert risk["id"] == "AIR-SEC-010", form
    assert risk["short_id"] == "ri-10"
    assert risk["mitigated_by"] and all(
        m.startswith(("AIR-PREV-", "AIR-DET-")) for m in risk["mitigated_by"]
    )
    assert risk["citation_uri"] == "aigf://risk/AIR-SEC-010"
    assert risk["sections"]
    compact = _structured(
        await client.call_tool("get_risk", {"id": "ri-10", "include_sections": False})
    )
    assert compact["sections"] == [] and compact["summary"]


@pytest.mark.anyio
async def test_wrong_kind_and_unknown_ids_are_structured_errors(client: Client) -> None:
    env = _error(await client.call_tool("get_risk", {"id": "AIR-PREV-020"}))
    assert env.code == "invalid_input" and "get_control" in (env.hint or "")
    env = _error(await client.call_tool("get_control", {"id": "ri-10"}))
    assert env.code == "invalid_input"
    env = _error(await client.call_tool("get_control", {"id": "AIR-PREV-999"}))
    assert env.code == "not_found" and env.hint


@pytest.mark.anyio
async def test_get_control_has_crosswalk_and_mitigates(client: Client) -> None:
    control = _structured(await client.call_tool("get_control", {"id": "mi-20"}))
    assert control["id"] == "AIR-PREV-020"
    assert "AIR-SEC-026" in control["mitigates"]
    frameworks = {r["framework"] for r in control["references"]}
    assert "nist-sp-800-53r5" in frameworks
    resolved = [r for r in control["references"] if r["title"]]
    assert resolved, "reference titles should resolve from the datasets"


@pytest.mark.anyio
async def test_map_risks_to_controls_by_ids_and_query(client: Client) -> None:
    m = _structured(
        await client.call_tool("map_risks_to_controls", {"risk_ids": ["ri-10", "bogus-id"]})
    )
    assert [r["id"] for r in m["risks"]] == ["AIR-SEC-010"]
    assert m["unresolved"] == ["bogus-id"]
    assert m["edges"] and all(e["risk_id"] == "AIR-SEC-010" for e in m["edges"])
    control_ids = {c["id"] for c in m["controls"]}
    assert {e["control_id"] for e in m["edges"]} == control_ids
    q = _structured(
        await client.call_tool("map_risks_to_controls", {"query": "prompt injection", "k": 3})
    )
    assert "AIR-SEC-010" in {r["id"] for r in q["risks"]}
    env = _error(await client.call_tool("map_risks_to_controls", {}))
    assert env.code == "invalid_input"


@pytest.mark.anyio
async def test_map_control_to_external_filters_frameworks(client: Client) -> None:
    cw = _structured(
        await client.call_tool(
            "map_control_to_external", {"id": "AIR-PREV-020", "frameworks": ["nist-sp-800-53r5"]}
        )
    )
    assert cw["frameworks"] == ["nist-sp-800-53r5"]
    assert cw["refs"] and all(r["framework"] == "nist-sp-800-53r5" for r in cw["refs"])
    env = _error(
        await client.call_tool(
            "map_control_to_external", {"id": "AIR-PREV-020", "frameworks": ["not-a-framework"]}
        )
    )
    assert env.code == "not_found"


@pytest.mark.anyio
async def test_search_framework_ranks_and_cites(client: Client) -> None:
    res = _structured(
        await client.call_tool("search_framework", {"query": "prompt injection", "k": 5})
    )
    assert res["hits"][0]["id"] == "AIR-SEC-010"
    assert res["hits"][0]["citation_uri"] == "aigf://risk/AIR-SEC-010"
    controls_only = _structured(
        await client.call_tool(
            "search_framework", {"query": "MCP server governance", "scope": "controls", "k": 3}
        )
    )
    assert controls_only["hits"] and all(
        h["id"].startswith(("AIR-PREV-", "AIR-DET-")) for h in controls_only["hits"]
    )
    assert "AIR-PREV-020" in {h["id"] for h in controls_only["hits"]}
    assert _error(await client.call_tool("search_framework", {"query": "  "})).code == (
        "invalid_input"
    )


@pytest.mark.anyio
async def test_reference_frameworks_and_server_info(client: Client) -> None:
    refs = _structured(await client.call_tool("list_reference_frameworks", {}))
    names = {f["name"] for f in refs["frameworks"]}
    assert {"nist-sp-800-53r5", "eu-ai-act", "owasp-llm", "iso-42001"} <= names
    assert all(f["entry_count"] > 0 for f in refs["frameworks"])
    info = _structured(await client.call_tool("server_info", {}))
    assert info["counts"]["risks"] == 23 and info["counts"]["controls"] == 23
    assert info["counts"]["risk_control_edges"] > 23
    assert info["upstream_commit"] and info["standard_version"]
    assert info["read_only"] is True


@pytest.mark.anyio
async def test_resources_serve_citable_markdown_and_index(client: Client) -> None:
    templates = (await client.list_resource_templates()).resource_templates
    assert {t.uri_template for t in templates} >= {
        "aigf://risk/{id}",
        "aigf://control/{id}",
        "aigf://reference/{framework}",
    }
    risk = await client.read_resource("aigf://risk/AIR-SEC-010")
    text = risk.contents[0].text  # type: ignore[union-attr]
    assert text.startswith("<!-- AIR-SEC-010 | Prompt Injection")
    assert "sequence: 10" in text
    control = await client.read_resource("aigf://control/mi-20")
    assert "MCP Server Security Governance" in control.contents[0].text  # type: ignore[union-attr]
    first_slug = state().controls.get("AIR-PREV-020").sections[0].slug  # type: ignore[union-attr]
    section = await client.read_resource(f"aigf://control/AIR-PREV-020/section/{first_slug}")
    assert section.contents[0].text.startswith("## ")  # type: ignore[union-attr]
    index = json.loads((await client.read_resource("aigf://index")).contents[0].text)  # type: ignore[union-attr]
    assert len(index["risks"]) == 23 and len(index["controls"]) == 23
    dataset = json.loads(
        (await client.read_resource("aigf://reference/nist-sp-800-53r5")).contents[0].text  # type: ignore[union-attr]
    )
    assert dataset["entries"]
    with pytest.raises(MCPError):
        await client.read_resource("aigf://risk/AIR-SEC-999")


@pytest.mark.anyio
async def test_prompts_are_registered(client: Client) -> None:
    prompts = (await client.list_prompts()).prompts
    assert {p.name for p in prompts} == {"assess_use_case", "control_gap_analysis"}
    got = await client.get_prompt("assess_use_case", {"description": "RAG chatbot"})
    assert "map_risks_to_controls" in got.messages[0].content.text  # type: ignore[union-attr]
