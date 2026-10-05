"""The shared command line, and the Host/Origin allow-list it hands the MCP SDK."""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from finos_mcp.core import build_server
from finos_mcp.core.cli import serve, transport_security

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "t", "version": "0"},
    },
}
ACCEPT = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


def _server() -> Any:
    return build_server("finos-test", version="0.0.1", instructions="test server")


def test_loopback_bind_needs_no_allow_list_and_no_warning() -> None:
    assert transport_security("127.0.0.1", [], []) == (None, None)


def test_public_bind_without_an_allow_list_warns() -> None:
    settings, warning = transport_security("0.0.0.0", [], [])
    assert settings is None and warning is not None and "--allowed-host" in warning


def test_allow_list_switches_header_checking_on_for_any_bind() -> None:
    settings, warning = transport_security("0.0.0.0", ["mcp.example.com"], ["https://a.example"])
    assert warning is None and settings is not None
    assert settings.enable_dns_rebinding_protection is True
    assert settings.allowed_hosts == ["mcp.example.com"]
    assert settings.allowed_origins == ["https://a.example"]


def test_origins_alone_are_not_silently_accepted() -> None:
    settings, warning = transport_security("0.0.0.0", [], ["https://a.example"])
    assert settings is None and warning is not None and "--allowed-host" in warning


def test_serve_passes_flags_and_environment_to_the_sdk(capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[dict[str, Any]] = []

    class Recorder:
        def run(self, **kwargs: Any) -> None:
            calls.append(kwargs)

    argv = ["--transport", "streamable-http", "--host", "0.0.0.0", "--allowed-host", "a.example"]
    env = {"FINOS_MCP_ALLOWED_HOSTS": "b.example:*, ", "FINOS_MCP_ALLOWED_ORIGINS": "https://b"}
    serve(lambda: Recorder(), prog="finos-mcp-test", default_port=8000, argv=argv, env=env)  # type: ignore[arg-type,return-value]
    settings = calls[0]["transport_security"]
    assert settings.allowed_hosts == ["a.example", "b.example:*"]
    assert settings.allowed_origins == ["https://b"]
    assert capsys.readouterr().err == ""

    serve(lambda: Recorder(), prog="finos-mcp-test", default_port=8000, argv=argv[:4], env={})  # type: ignore[arg-type,return-value]
    assert "transport_security" not in calls[1]
    assert "not checking Host or Origin" in capsys.readouterr().err

    serve(lambda: Recorder(), prog="finos-mcp-test", default_port=8000, argv=[], env={})  # type: ignore[arg-type,return-value]
    assert calls[2] == {"transport": "stdio"}


def test_a_forged_host_is_refused_once_an_allow_list_is_set() -> None:
    """Bound to 0.0.0.0 the SDK checks nothing by default: a request carrying another
    site's Host and Origin is served. With the allow-list it is refused."""
    forged = {**ACCEPT, "host": "evil.example", "origin": "http://evil.example"}

    open_app = _server().streamable_http_app(host="0.0.0.0")
    with TestClient(open_app) as client:
        assert client.post("/mcp", json=INITIALIZE, headers=forged).status_code == 200

    settings, _ = transport_security("0.0.0.0", ["mcp.example.com"], ["https://app.example"])
    guarded = _server().streamable_http_app(host="0.0.0.0", transport_security=settings)
    with TestClient(guarded) as client:
        assert client.post("/mcp", json=INITIALIZE, headers=forged).status_code in {403, 421}
        allowed = {**ACCEPT, "host": "mcp.example.com", "origin": "https://app.example"}
        assert client.post("/mcp", json=INITIALIZE, headers=allowed).status_code == 200
