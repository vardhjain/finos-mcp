"""End-to-end tests of the safety stack through the real in-memory MCP client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from mcp.client import Client
from mcp.shared.exceptions import MCPError
from pydantic import BaseModel

from finos_mcp.core import (
    AuditLog,
    ErrorEnvelope,
    Metrics,
    RateLimit,
    SafetyPolicy,
    build_server,
    not_found,
    register_server_info,
    register_tool,
    runtime_for,
)
from finos_mcp.core.errors import RATE_LIMITED_CODE


class Echo(BaseModel):
    text: str
    length: int


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_server(
    tmp_path: Path, clock: FakeClock, policy: SafetyPolicy | None = None
) -> tuple[Any, Path]:
    audit_path = tmp_path / "audit.jsonl"
    pol = policy or SafetyPolicy(max_input_bytes=300, max_output_bytes=2048)
    server = build_server(
        "finos-test",
        version="0.0.1",
        instructions="test server",
        policy=pol,
        audit=AuditLog("finos-test", path=audit_path),
        metrics=Metrics(),
        clock=clock,
    )

    def echo(text: str) -> Echo:
        """Echo text back with its length."""
        return Echo(text=text, length=len(text))

    def missing(id: str) -> Echo:
        """Always raises a structured not_found."""
        raise not_found("widget", id, hint="try list_widgets")

    def big(n: int) -> Echo:
        """Return a large payload."""
        return Echo(text="x" * n, length=n)

    register_tool(server, echo)
    register_tool(
        server, missing, name="get_widget", limit=RateLimit(calls=60, window_s=60, burst=2)
    )
    register_tool(server, big)
    register_server_info(
        server,
        standard="TEST",
        standard_version="1",
        upstream_repo="example/repo",
        upstream_ref="main",
        upstream_commit="abc",
        counts=lambda: {"widgets": 3},
    )
    return server, audit_path


def read_audit(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


@pytest.mark.anyio
async def test_structured_output_and_read_only_annotations(tmp_path: Path) -> None:
    server, _ = make_server(tmp_path, FakeClock())
    async with Client(server, raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
        names = {t.name for t in tools}
        assert {"echo", "get_widget", "big", "server_info"} <= names
        for t in tools:
            assert t.annotations is not None and t.annotations.read_only_hint is True
            assert t.annotations.destructive_hint is False
        echo = next(t for t in tools if t.name == "echo")
        assert echo.output_schema is not None and "length" in echo.output_schema["properties"]
        result = await client.call_tool("echo", {"text": "hi"})
        assert result.is_error is False
        assert result.structured_content == {"text": "hi", "length": 2}


@pytest.mark.anyio
async def test_structured_error_envelope_reaches_model(tmp_path: Path) -> None:
    server, audit_path = make_server(tmp_path, FakeClock())
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool("get_widget", {"id": "nope"})
        assert result.is_error is True
        text = result.content[0].text  # type: ignore[union-attr]
        env = ErrorEnvelope.parse_text(text)
        assert env is not None and env.code == "not_found" and env.hint == "try list_widgets"
    records = [r for r in read_audit(audit_path) if r.get("tool") == "get_widget"]
    assert records and records[-1]["outcome"] == "tool_error:not_found"
    assert "args_sha256" in records[-1] and "args" not in records[-1]


@pytest.mark.anyio
async def test_input_size_cap(tmp_path: Path) -> None:
    server, audit_path = make_server(tmp_path, FakeClock())
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool("echo", {"text": "y" * 400})
        assert result.is_error is True
        env = ErrorEnvelope.parse_text(result.content[0].text)  # type: ignore[union-attr]
        assert env is not None and env.code == "input_too_large"
        assert env.details["limit_bytes"] == 300
    assert read_audit(audit_path)[-1]["outcome"] == "input_too_large"


@pytest.mark.anyio
async def test_output_size_cap(tmp_path: Path) -> None:
    server, _ = make_server(tmp_path, FakeClock())
    async with Client(server, raise_exceptions=True) as client:
        ok = await client.call_tool("big", {"n": 100})
        assert ok.is_error is False
        result = await client.call_tool("big", {"n": 5000})
        assert result.is_error is True
        env = ErrorEnvelope.parse_text(result.content[0].text)  # type: ignore[union-attr]
        assert env is not None and env.code == "output_too_large"


@pytest.mark.anyio
async def test_rate_limit_is_json_rpc_error_and_recovers(tmp_path: Path) -> None:
    clock = FakeClock()
    server, audit_path = make_server(tmp_path, clock)
    async with Client(server, raise_exceptions=True) as client:
        await client.call_tool("get_widget", {"id": "a"})
        await client.call_tool("get_widget", {"id": "b"})
        with pytest.raises(MCPError) as excinfo:
            await client.call_tool("get_widget", {"id": "c"})
        assert excinfo.value.code == RATE_LIMITED_CODE
        assert excinfo.value.error.data["tool"] == "get_widget"
        assert excinfo.value.error.data["retry_after_s"] > 0
        clock.now += 2.0  # 1 call/s refill
        again = await client.call_tool("get_widget", {"id": "d"})
        assert again.is_error is True  # not_found, but it ran
    outcomes = [r["outcome"] for r in read_audit(audit_path) if r.get("tool") == "get_widget"]
    assert outcomes == [
        "tool_error:not_found",
        "tool_error:not_found",
        "rate_limited",
        "tool_error:not_found",
    ]
    snap = runtime_for(server).metrics.snapshot()["get_widget"]
    assert snap["calls"] == 4 and snap["rate_limited"] == 1 and snap["errors"] == 4


@pytest.mark.anyio
async def test_server_info_reports_counts_and_latency(tmp_path: Path) -> None:
    server, _ = make_server(tmp_path, FakeClock())
    async with Client(server, raise_exceptions=True) as client:
        await client.call_tool("echo", {"text": "warm"})
        info = (await client.call_tool("server_info", {})).structured_content
        assert info is not None
        assert info["read_only"] is True
        assert info["counts"] == {"widgets": 3}
        assert "echo" in info["latency"] and info["latency"]["echo"]["calls"] == 1
        assert set(info["tools"]) == {"big", "echo", "get_widget", "server_info"}


@pytest.mark.anyio
async def test_gate_refuses_non_read_only_tool(tmp_path: Path) -> None:
    server, _ = make_server(tmp_path, FakeClock())

    @server.tool()  # bypasses register_tool: no annotations
    def rogue(x: int) -> int:
        """A tool registered without read-only annotations."""
        return x

    async with Client(server, raise_exceptions=True) as client:
        with pytest.raises(MCPError) as excinfo:
            await client.list_tools()
        assert "rogue" in excinfo.value.error.data["tools"]


@pytest.mark.anyio
async def test_audit_records_every_request(tmp_path: Path) -> None:
    server, audit_path = make_server(tmp_path, FakeClock())
    async with Client(server, raise_exceptions=True) as client:
        await client.list_tools()
        await client.call_tool("echo", {"text": "a"})
    methods = [r["method"] for r in read_audit(audit_path)]
    # The in-process client handshakes with server/discover; stdio/HTTP clients send initialize.
    assert "tools/list" in methods and "tools/call" in methods
    assert any(m in methods for m in ("initialize", "server/discover"))
    for r in read_audit(audit_path):
        assert r["server"] == "finos-test" and "ts" in r and "duration_ms" in r


def test_policy_env_can_only_tighten() -> None:
    pol = SafetyPolicy(
        max_input_bytes=1000, default_limit=RateLimit(calls=100, window_s=60, burst=10)
    )
    looser = pol.tightened_from_env(
        {"FINOS_MCP_MAX_INPUT_BYTES": "5000", "FINOS_MCP_RATE_CALLS": "500"}
    )
    assert looser.max_input_bytes == 1000 and looser.default_limit.calls == 100
    tighter = pol.tightened_from_env(
        {
            "FINOS_MCP_MAX_INPUT_BYTES": "512",
            "FINOS_MCP_RATE_CALLS": "5",
            "FINOS_MCP_RATE_BURST": "1",
        }
    )
    assert tighter.max_input_bytes == 512
    assert tighter.default_limit.calls == 5 and tighter.default_limit.burst == 1
    assert pol.tightened_from_env({"FINOS_MCP_AUDIT_RAW_ARGS": "1"}).audit_hash_inputs is False
