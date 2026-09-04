"""FDC3 server tests through the in-memory MCP client."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from mcp.client import Client

from finos_mcp.core import ErrorEnvelope
from finos_mcp.fdc3.server import create_server

INSTRUMENT = {"type": "fdc3.instrument", "id": {"ticker": "AAPL"}, "name": "Apple"}


@pytest.fixture(scope="module")
def server() -> Any:
    return create_server()


@pytest.fixture
async def client(server: Any) -> AsyncIterator[Client]:
    async with Client(server, raise_exceptions=True) as c:
        yield c


def _ok(result: Any) -> dict[str, Any]:
    assert result.is_error is False, result.content
    assert result.structured_content is not None
    return dict(result.structured_content)


def _err(result: Any) -> ErrorEnvelope:
    assert result.is_error is True
    env = ErrorEnvelope.parse_text(result.content[0].text)
    assert env is not None
    return env


@pytest.mark.anyio
async def test_tools_are_typed_and_read_only(client: Client) -> None:
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == {
        "list_intents",
        "get_intent",
        "list_context_types",
        "get_context_schema",
        "validate_context",
        "suggest_intent",
        "find_intents_by_context",
        "search_intents",
        "server_info",
    }
    assert all(t.annotations and t.annotations.read_only_hint for t in tools)
    assert all(t.output_schema for t in tools)


@pytest.mark.anyio
async def test_list_intents_and_filter(client: Client) -> None:
    res = _ok(await client.call_tool("list_intents", {}))
    names = {i["name"] for i in res["intents"]}
    assert {"ViewChart", "ViewInstrument", "StartChat", "ViewContact"} <= names
    assert len(res["intents"]) == 19
    no_dep = _ok(await client.call_tool("list_intents", {"include_deprecated": False}))
    assert "ViewContact" not in {i["name"] for i in no_dep["intents"]}
    for_instr = _ok(await client.call_tool("list_intents", {"context_type": "fdc3.instrument"}))
    assert {"ViewInstrument", "ViewChart", "ViewQuote", "ViewNews"} <= {
        i["name"] for i in for_instr["intents"]
    }
    alias = _ok(await client.call_tool("find_intents_by_context", {"context_type": "instrument"}))
    assert alias == for_instr
    assert _err(await client.call_tool("list_intents", {"context_type": "fdc3.nope"})).code == (
        "not_found"
    )


@pytest.mark.anyio
async def test_get_intent(client: Client) -> None:
    vc = _ok(await client.call_tool("get_intent", {"name": "viewchart"}))
    assert vc["name"] == "ViewChart"
    assert sorted(vc["contexts"]) == [
        "fdc3.chart",
        "fdc3.instrument",
        "fdc3.instrumentList",
        "fdc3.portfolio",
        "fdc3.position",
    ]
    assert vc["citation_uri"] == "fdc3://intent/ViewChart"
    env = _err(await client.call_tool("get_intent", {"name": "ViewChrt"}))
    assert env.code == "not_found" and "ViewChart" in (env.hint or "")


@pytest.mark.anyio
async def test_context_types_and_schema(client: Client) -> None:
    types = _ok(await client.call_tool("list_context_types", {}))
    all_types = {t["type"] for t in types["context_types"]}
    assert {"fdc3.instrument", "fdc3.contact", "fdc3.nothing", "fdc3.chart"} <= all_types
    assert len(all_types) == 28
    instr = next(t for t in types["context_types"] if t["type"] == "fdc3.instrument")
    assert "ViewInstrument" in instr["used_by_intents"]
    schema = _ok(await client.call_tool("get_context_schema", {"type": "Instrument"}))
    assert schema["type"] == "fdc3.instrument"
    assert "id" in schema["required"]
    assert {p["name"] for p in schema["properties"]} >= {"type", "id", "name"}
    assert schema["json_schema"]["$id"].endswith("/context/instrument.schema.json")
    assert schema["example"] and schema["example"]["type"] == "fdc3.instrument"


@pytest.mark.anyio
async def test_validate_context(client: Client) -> None:
    good = _ok(await client.call_tool("validate_context", {"context": INSTRUMENT}))
    assert good["valid"] is True and good["issues"] == []
    bad = _ok(
        await client.call_tool(
            "validate_context", {"context": {"type": "fdc3.instrument", "id": "AAPL"}}
        )
    )
    assert bad["valid"] is False
    assert any(i["json_path"] == "$.id" for i in bad["issues"])
    env = _err(await client.call_tool("validate_context", {"context": {"name": "x"}}))
    assert env.code == "invalid_input"
    explicit = _ok(
        await client.call_tool(
            "validate_context", {"context": {"name": "x"}, "type": "fdc3.instrument"}
        )
    )
    assert explicit["valid"] is False
    assert (
        _err(await client.call_tool("validate_context", {"context": {"type": "fdc3.zzz"}})).code
        == "not_found"
    )


@pytest.mark.anyio
async def test_suggest_intent(client: Client) -> None:
    res = _ok(await client.call_tool("suggest_intent", {"context": INSTRUMENT}))
    assert res["detected_by"] == "type_field" and res["context_type"] == "fdc3.instrument"
    names = [s["name"] for s in res["suggestions"]]
    assert names[0] == "ViewInstrument"
    assert {"ViewChart", "ViewQuote", "ViewNews", "ViewAnalysis", "ViewHoldings"} <= set(names)
    assert res["validation"]["valid"] is True
    goal = _ok(
        await client.call_tool(
            "suggest_intent", {"context": INSTRUMENT, "goal": "show a price chart"}
        )
    )
    assert goal["suggestions"][0]["name"] == "ViewChart"
    by_type = _ok(await client.call_tool("suggest_intent", {"context_type": "fdc3.contact"}))
    assert by_type["detected_by"] == "explicit"
    assert {"ViewContact", "StartChat", "StartCall"} <= {s["name"] for s in by_type["suggestions"]}
    structural = _ok(
        await client.call_tool(
            "suggest_intent", {"context": {"id": {"email": "a@b.co"}, "name": "Ann"}}
        )
    )
    assert structural["detected_by"] == "structural_match"
    assert _err(await client.call_tool("suggest_intent", {})).code == "invalid_input"


@pytest.mark.anyio
async def test_resources_and_server_info(client: Client) -> None:
    schema = json.loads(
        (await client.read_resource("fdc3://schema/fdc3.instrument")).contents[0].text
    )  # type: ignore[union-attr]
    own = next(part for part in schema["allOf"] if "properties" in part)
    assert own["properties"]["type"]["const"] == "fdc3.instrument"
    doc = (await client.read_resource("fdc3://intent/ViewChart")).contents[0].text  # type: ignore[union-attr]
    assert doc.startswith("<!-- ViewChart | FDC3")
    assert "Possible Contexts" in doc
    table = json.loads((await client.read_resource("fdc3://intents")).contents[0].text)  # type: ignore[union-attr]
    assert table["count"] == 19
    info = _ok(await client.call_tool("server_info", {}))
    assert info["read_only"] is True and info["standard_version"] == "2.2.3"
    assert info["counts"]["intents"] == 19
