"""Regression checks for copy-paste MCP client examples.

Never contacts PyPI, starts paid APIs, or starts a persistent MCP server.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
COMPONENTS = ("aigf", "cdm", "fdc3")
SERVER_IDS = {f"finos-{name}" for name in COMPONENTS}
PINNED = "0.3.1"  # Last public release tested when the examples were authored.


def test_mcp_client_samples_have_correct_schema_and_real_console_scripts() -> None:
    for filename, wrapper in (
        ("claude_desktop_config.json", "mcpServers"),
        ("copilot_mcp.json", "mcpServers"),
        ("vscode_mcp.json", "servers"),
    ):
        sample = json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))
        assert set(sample) == {wrapper}, filename
        servers = sample[wrapper]
        assert set(servers) == SERVER_IDS
        for component in COMPONENTS:
            entry = servers[f"finos-{component}"]
            assert entry["command"] == "uvx"
            assert entry["args"] == [
                "--python",
                "3.12",
                f"finos-mcp-{component}=={PINNED}",
            ]
            assert set(entry) == (
                {"type", "command", "args"} if wrapper == "servers" else {"command", "args"}
            )
            if wrapper == "servers":
                assert entry["type"] == "stdio"


def test_mcp_client_examples_have_no_secrets_or_remote_execution() -> None:
    for filename in ("claude_desktop_config.json", "copilot_mcp.json", "vscode_mcp.json"):
        data = json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))
        for server in next(iter(data.values())).values():
            assert "env" not in server
            assert "url" not in server
            assert "headers" not in server
            assert server["command"] == "uvx"


def test_configured_console_entrypoints_support_help_without_network() -> None:
    # The workspace install is exercised offline, while the earlier independent
    # verify-public-pypi workflow verifies real pinned distributions separately.
    for component in COMPONENTS:
        command = shutil.which(f"finos-mcp-{component}")
        assert command is not None
        result = subprocess.run(
            [command, "--help"],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        assert result.returncode == 0, (component, result.stderr)
        assert "usage:" in result.stdout.lower(), component
