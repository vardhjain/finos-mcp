"""CDM server tests through the in-memory MCP client, including dual-format validation."""

from __future__ import annotations

import copy
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from mcp.client import Client

from finos_mcp.cdm.registry import get_registry
from finos_mcp.cdm.server import create_server
from finos_mcp.cdm.validate import detect_format
from finos_mcp.core import ErrorEnvelope, RateLimit, runtime_for


@pytest.fixture(scope="module")
def server() -> Any:
    srv = create_server()
    # These tests exercise behaviour, not the rate policy (covered in core): validating
    # all vendored samples back to back would otherwise trip validate_object's 30/min limit.
    rt = runtime_for(srv)
    rt.policy.default_limit = RateLimit(calls=1_000_000, window_s=1.0, burst=1_000_000)
    rt.policy.per_tool.clear()
    return srv


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


def _samples(fmt: str) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for s in get_registry().samples():
        if s.format == fmt:
            out.append((s.name, json.loads(Path(s.path).read_text(encoding="utf-8"))))
    return out


@pytest.mark.anyio
async def test_tools_are_typed_and_read_only(client: Client) -> None:
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == {
        "describe_type",
        "list_types",
        "list_products",
        "validate_object",
        "explain_event",
        "search_types",
        "get_sample",
        "list_samples",
        "server_info",
    }
    assert all(t.annotations and t.annotations.read_only_hint for t in tools)
    assert all(t.output_schema for t in tools)


@pytest.mark.anyio
async def test_describe_type(client: Client) -> None:
    ts = _ok(await client.call_tool("describe_type", {"name": "TradeState"}))
    assert ts["namespace"] == "cdm.event.common" and ts["root_type"] is True
    trade = next(f for f in ts["fields"] if f["name"] == "trade")
    assert trade["cardinality"] == "1..1" and trade["type"] == "Trade"
    assert "BusinessEvent" in ts["used_by"]
    assert ts["schema_uri"] == "cdm://schema/TradeState"
    fqn = _ok(await client.call_tool("describe_type", {"name": "cdm.event.common.TradeState"}))
    assert fqn["name"] == "TradeState"
    payout = _ok(await client.call_tool("describe_type", {"name": "Payout"}))
    assert payout["kind"] == "choice" and "InterestRatePayout" in payout["alternatives"]
    env = _err(await client.call_tool("describe_type", {"name": "TradeStat"}))
    assert env.code == "not_found" and "TradeState" in (env.hint or "")


@pytest.mark.anyio
async def test_list_types_and_products(client: Client) -> None:
    roots = _ok(await client.call_tool("list_types", {"root_only": True, "page_size": 100}))
    assert roots["total"] == 16 and all(t["root_type"] for t in roots["items"])
    enums = _ok(
        await client.call_tool(
            "list_types", {"kind": "enum", "namespace": "cdm.base", "page_size": 5}
        )
    )
    assert enums["items"] and all(t["kind"] == "enum" for t in enums["items"])
    products = _ok(await client.call_tool("list_products", {}))
    names = {e["name"]: e for e in products["entries"]}
    assert {"NonTransferableProduct", "EconomicTerms", "Payout"} <= set(names)
    assert names["InterestRatePayout"]["role"] == "payout_alternative"
    assert names["InterestRatePayout"]["samples"], "vendored IRS samples should be listed"


@pytest.mark.anyio
async def test_validate_rune_samples_normalise_cleanly(client: Client) -> None:
    """Every official 7.2.0 Rune sample normalises without structural errors.

    Pinned upstream discrepancy: the published cdm-json-schema 7.2.0 marks fields as
    required that CDM's own 7.2.0 function-output samples omit (ClosedState.activityDate,
    ExecutionDetails, Underlier, DateAdjustments, ExerciseNoticeGiver). The validator
    reports those truthfully; anything *other* than a `required` miss would indicate a
    defect in the Rune-to-legacy normalisation, so that is what this test forbids.
    When upstream fixes the schema or the samples, EXPECTED_VALID below moves.
    """
    samples = _samples("rune")
    assert samples
    valid = 0
    non_required: list[tuple[str, str, str]] = []
    required_fields: set[str] = set()
    for name, doc in samples:
        assert detect_format(doc) == "rune"
        report = _ok(await client.call_tool("validate_object", {"object": doc}))
        assert report["format_detected"] == "rune"
        assert "Rune normalisation" in report["validator"]
        assert report["stats"]["nodes_normalised"] > 10
        valid += report["valid"]
        for issue in report["issues"]:
            if issue["kind"] == "required":
                required_fields.add(issue["message"].split("'")[1])
            else:
                non_required.append((name, issue["json_path"], issue["message"]))
    assert not non_required, non_required[:5]
    assert required_fields <= EXPECTED_REQUIRED_MISSES, required_fields - EXPECTED_REQUIRED_MISSES
    assert valid == EXPECTED_VALID, (
        f"{valid}/{len(samples)} valid; update EXPECTED_VALID if upstream changed"
    )


EXPECTED_VALID = 10
EXPECTED_REQUIRED_MISSES = {
    "activityDate",
    "executionDetails",
    "underlier",
    "dateAdjustments",
    "exerciseNoticeGiver",
}


@pytest.mark.anyio
async def test_validate_rune_mutations_report_document_paths(client: Client) -> None:
    _name, doc = next(s for s in _samples("rune") if s[0].startswith("execution__execution-basis"))
    # 1. required field removed from a nested Rune object
    broken = copy.deepcopy(doc)
    broken["after"][0].pop("trade")
    report = _ok(await client.call_tool("validate_object", {"object": broken}))
    assert report["valid"] is False
    kinds = {(i["json_path"], i["kind"]) for i in report["issues"]}
    assert ("$.after[0]", "required") in kinds, kinds
    # 2. wrong choice alternative name
    broken = copy.deepcopy(doc)
    payout = broken["instruction"][0]["primitiveInstruction"]["execution"]["product"][
        "economicTerms"
    ]["payout"][0]
    payout["@type"] = "cdm.product.asset.NoSuchPayout"
    report = _ok(await client.call_tool("validate_object", {"object": broken}))
    assert any(i["kind"] == "enum" and "NoSuchPayout" in i["message"] for i in report["issues"])
    assert any(i["json_path"].endswith("payout[0].@type") for i in report["issues"])
    # 3. type error inside a payout: paths map back into the Rune document (no wrapper key)
    broken = copy.deepcopy(doc)
    payout = broken["instruction"][0]["primitiveInstruction"]["execution"]["product"][
        "economicTerms"
    ]["payout"][0]
    payout["payerReceiver"]["payer"] = 42
    report = _ok(await client.call_tool("validate_object", {"object": broken}))
    paths = [i["json_path"] for i in report["issues"]]
    assert any(p.endswith("payout[0].payerReceiver.payer") for p in paths), paths
    assert not any("InterestRatePayout" in p for p in paths)


@pytest.mark.anyio
async def test_validate_legacy_sample_against_matching_vintage(client: Client) -> None:
    samples = _samples("legacy")
    assert samples
    _name, doc = samples[0]
    assert detect_format(doc) == "legacy"
    primary = _ok(
        await client.call_tool("validate_object", {"object": doc, "type": "BusinessEvent"})
    )
    assert primary["format_detected"] == "legacy" and "6.27.0" in " ".join(primary["warnings"])
    vintage = _ok(
        await client.call_tool(
            "validate_object", {"object": doc, "type": "BusinessEvent", "schema_version": "6.27.0"}
        )
    )
    assert "6.27.0" in vintage["validator"]
    assert vintage["stats"]["schema_files"] > 1000
    env = _err(
        await client.call_tool(
            "validate_object", {"object": doc, "type": "BusinessEvent", "schema_version": "1.0.0"}
        )
    )
    assert env.code == "not_found"


@pytest.mark.anyio
async def test_validate_errors(client: Client) -> None:
    env = _err(await client.call_tool("validate_object", {"object": {"eventDate": "2020-01-01"}}))
    assert env.code == "invalid_input" and "type" in env.message
    env = _err(await client.call_tool("validate_object", {"object": {}, "type": "Nope"}))
    assert env.code == "not_found"


@pytest.mark.anyio
async def test_explain_event_from_document_and_name(client: Client) -> None:
    _name, doc = next(s for s in _samples("rune") if s[0].startswith("execution__execution-basis"))
    ex = _ok(await client.call_tool("explain_event", {"event": doc}))
    assert ex["qualifier"] == "Execution"
    assert ex["qualify_function"]["name"] == "Qualify_Execution"
    assert "execution" in ex["instruction_types"]
    assert ex["after_trade_count"] >= 1
    assert ex["after_products"][0]["payout_types"]
    by_name = _ok(await client.call_tool("explain_event", {"qualifier": "Termination"}))
    assert by_name["qualify_function"]["name"] == "Qualify_Termination"
    assert by_name["qualify_function"]["condition_text"]
    unknown = _ok(await client.call_tool("explain_event", {"qualifier": "Teleportation"}))
    assert unknown["qualify_function"] is None and unknown["notes"]
    assert _err(await client.call_tool("explain_event", {})).code == "invalid_input"


@pytest.mark.anyio
async def test_search_samples_resources_and_info(client: Client) -> None:
    hits = _ok(
        await client.call_tool("search_types", {"query": "floating rate specification", "k": 5})
    )
    assert "FloatingRateSpecification" in {h["id"] for h in hits["result"]}
    samples = _ok(await client.call_tool("list_samples", {"format": "rune"}))
    first = samples["samples"][0]["name"]
    sample = _ok(await client.call_tool("get_sample", {"name": first}))
    assert sample["json_document"]["@type"].endswith("BusinessEvent")
    schema = json.loads((await client.read_resource("cdm://schema/TradeState")).contents[0].text)  # type: ignore[union-attr]
    assert schema["required"] == ["trade"]
    rule = (await client.read_resource("cdm://qualify/Execution")).contents[0].text  # type: ignore[union-attr]
    assert rule.startswith("# Qualify_Execution")
    index = json.loads((await client.read_resource("cdm://index")).contents[0].text)  # type: ignore[union-attr]
    assert len(index["qualifiers"]) == 35 and "6.27.0" in index["schema_versions"]
    info = _ok(await client.call_tool("server_info", {}))
    assert info["counts"]["root_types"] == 16 and info["counts"]["qualify_functions"] == 35
    assert info["counts"]["schemas"] > 1100 and info["standard_version"] == "7.2.0"
