"""Spawn the real console script over stdio: proves stdout carries only protocol frames."""

from __future__ import annotations

import os
import sys

import pytest
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters


@pytest.mark.anyio
async def test_console_script_over_stdio(tmp_path: object) -> None:
    env = {**os.environ, "PYTHONUTF8": "1", "FINOS_MCP_AUDIT_PATH": str(tmp_path) + "/audit.jsonl"}
    params = StdioServerParameters(command=sys.executable, args=["-m", "finos_mcp.aigf"], env=env)
    async with Client(params, raise_exceptions=True) as client:
        tools = (await client.list_tools()).tools
        assert any(t.name == "get_control" for t in tools)
        result = await client.call_tool("get_control", {"id": "mi-20", "include_sections": False})
        assert result.is_error is False
        assert result.structured_content is not None
        assert result.structured_content["id"] == "AIR-PREV-020"
        hits = await client.call_tool("search_framework", {"query": "data poisoning", "k": 3})
        assert hits.structured_content is not None and hits.structured_content["hits"]
