"""Spawn the real console script over streamable-http.

This is the transport a container deployment uses, and the only one where the rate
limiter keys on the ``Mcp-Session-Id`` header rather than the single stdio session,
so it needs its own coverage rather than being assumed to work.
"""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from mcp.client import Client

STARTUP_TIMEOUT_S = 300  # cold import of the servers is slow on an antivirus-scanned disk


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextlib.contextmanager
def _server(tmp_path: Path) -> Iterator[str]:
    port = _free_port()
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "FINOS_MCP_AUDIT_PATH": str(tmp_path / "audit.jsonl"),
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "finos_mcp.aigf",
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                out, err = proc.communicate()
                pytest.fail(f"server exited rc={proc.returncode}\n{(err or out)[-2000:]}")
            with socket.socket() as s:
                s.settimeout(1)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.5)
        else:
            pytest.fail("server did not open its port in time")
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.anyio
async def test_console_script_over_streamable_http(tmp_path: Path) -> None:
    with _server(tmp_path) as url:
        async with Client(url, raise_exceptions=True) as client:
            tools = (await client.list_tools()).tools
            assert {"get_control", "search_framework", "server_info"} <= {t.name for t in tools}
            assert all(t.annotations and t.annotations.read_only_hint for t in tools)

            result = await client.call_tool(
                "get_control", {"id": "mi-20", "include_sections": False}
            )
            assert result.is_error is False
            assert result.structured_content is not None
            assert result.structured_content["id"] == "AIR-PREV-020"

            # Resources must be readable over HTTP too: they are the citation surface.
            res = await client.read_resource("aigf://control/AIR-PREV-020")
            assert "MCP Server Security Governance" in res.contents[0].text  # type: ignore[union-attr]

    audit = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert '"tool": "get_control"' in audit
    # Over HTTP the limiter keys on the session header, not the stdio placeholder.
    assert '"session": "local"' not in audit
