"""Validate the shared Claude Code and portable MCP plugin package without network access."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "finos-mcp"
PACKAGES = {
    "finos-aigf": "finos-mcp-aigf",
    "finos-cdm": "finos-mcp-cdm",
    "finos-fdc3": "finos-mcp-fdc3",
}
PIN = "0.3.2"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    portable = load(PLUGIN / "plugin.json")
    portable_mcp = load(PLUGIN / "mcp.json")
    claude = load(PLUGIN / ".claude-plugin" / "plugin.json")
    claude_mcp = load(PLUGIN / ".mcp.json")
    claude_market = load(ROOT / ".claude-plugin" / "marketplace.json")
    codex_market = load(ROOT / ".agents" / "plugins" / "marketplace.json")

    assert portable["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert portable_mcp["$schema"] == "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    assert portable["name"] == claude["name"] == "finos-mcp"
    assert portable["version"] == claude["version"]
    assert portable["extensions"]["com.openai"]["requires_local_executor"] is True

    assert set(portable_mcp["mcpServers"]) == set(claude_mcp["mcpServers"]) == set(PACKAGES)
    for key, package in PACKAGES.items():
        args = ["--python", "3.12", f"{package}=={PIN}"]
        modern = portable_mcp["mcpServers"][key]
        legacy = claude_mcp["mcpServers"][key]
        assert modern == {"type": "stdio", "command": "uvx", "args": args}
        assert legacy == {"command": "uvx", "args": args}

        skill_file = PLUGIN / "skills" / key / "SKILL.md"
        skill_text = skill_file.read_text(encoding="utf-8")
        assert skill_text.startswith(f"---\nname: {key}\ndescription: ")
        assert skill_text.count("\n---\n") >= 1

    assert claude_market["name"] == codex_market["name"] == "finos-mcp"
    assert claude_market["plugins"][0]["source"] == "./plugins/finos-mcp"
    assert codex_market["plugins"][0]["source"]["path"] == "./plugins/finos-mcp"
    assert claude_market["plugins"][0]["name"] == "finos-mcp"
    assert codex_market["plugins"][0]["name"] == "finos-mcp"

    print("OK: plugin manifests, marketplaces, skills and pinned MCP servers")


if __name__ == "__main__":
    main()
