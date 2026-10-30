"""Exercise published stdio MCP tools using the commands in both plugin manifests.

Uses JSON-RPC directly so the smoke test requires no model or API key.
Run after installing uv and Python 3.12:
    python scripts/smoke_plugin_mcp.py
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "finos-mcp"
CASES = json.loads((ROOT / "examples" / "try_it_cases.json").read_text(encoding="utf-8"))
TIMEOUT = 180


class MCPClient:
    """Tiny test-only MCP stdio JSON-RPC client with bounded reads."""

    def __init__(self, command: str, args: list[str]) -> None:
        self.proc = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.lines: queue.Queue[str | None] = queue.Queue()
        self.reader = threading.Thread(target=self._read_stdout, daemon=True)
        self.reader.start()
        self.next_id = 0

    def _read_stdout(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def send(self, message: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self.next_id += 1
        request_id = self.next_id
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        while True:
            try:
                line = self.lines.get(timeout=TIMEOUT)
            except queue.Empty as exc:
                raise TimeoutError(f"MCP {method} did not respond in {TIMEOUT}s") from exc
            if line is None:
                raise RuntimeError(f"MCP server exited while waiting for {method}")
            try:
                response = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AssertionError(f"Non-JSON data on stdio: {line!r}") from exc
            if response.get("id") != request_id:
                # Notifications may arrive between JSON-RPC replies.
                if "id" not in response:
                    continue
                raise AssertionError(f"Unexpected response id: {response!r}")
            if "error" in response:
                raise AssertionError(f"MCP {method}: {response['error']!r}")
            return response["result"]

    def close(self) -> None:
        if self.proc.stdin:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        if self.proc.returncode not in (0, -15):
            print(f"Note: stdio server stopped with code {self.proc.returncode}")


def check(config: str, server_key: str) -> None:
    manifest = json.loads((PLUGIN / config).read_text(encoding="utf-8"))
    server = manifest["mcpServers"][server_key]
    if "type" in server:
        assert server["type"] == "stdio"
    client = MCPClient(server["command"], server["args"])
    try:
        client.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "finos-plugin-smoke", "version": "0.1.0"},
            },
        )
        client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools = client.request("tools/list", {})
        case = CASES[server_key.removeprefix("finos-")]
        assert case["tool"] in {tool["name"] for tool in tools["tools"]}
        result = client.request(
            "tools/call", {"name": case["tool"], "arguments": case["arguments"]}
        )
        assert result.get("isError", False) is False, result
        output: Any = result.get("structuredContent")
        assert isinstance(output, dict), f"No structured tool result: {result}"
        actual: Any = output
        for step in case["expect"]["path"]:
            actual = actual[step]
        assert actual == case["expect"]["equals"], (config, server_key, actual)
        print(f"PASS: {config} -> {server_key}/{case['tool']} -> {actual}")
    finally:
        client.close()


def main() -> None:
    for config in ("mcp.json", ".mcp.json"):
        for server_key in ("finos-aigf", "finos-cdm", "finos-fdc3"):
            check(config, server_key)


if __name__ == "__main__":
    main()
