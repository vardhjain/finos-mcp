"""Validate the shared Claude Code and portable MCP plugin package without network access."""

import json
import os
import struct
import tomllib
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
        args = [
            "--no-config",
            "run",
            "--project",
            "${CLAUDE_PLUGIN_ROOT}",
            "--frozen",
            "--default-index",
            "https://pypi.org/simple",
            "--python",
            "3.12",
            package,
        ]
        modern = portable_mcp["mcpServers"][key]
        legacy = claude_mcp["mcpServers"][key]
        assert modern == {
            "type": "stdio",
            "command": "uv",
            "args": [a.replace("${CLAUDE_PLUGIN_ROOT}", "${PLUGIN_ROOT}") for a in args],
        }
        assert legacy == {"command": "uv", "args": args}

        skill_file = PLUGIN / "skills" / key / "SKILL.md"
        skill_text = skill_file.read_text(encoding="utf-8")
        assert skill_text.startswith(f"---\nname: {key}\ndescription: ")
        assert skill_text.count("\n---\n") >= 1

    assert claude_market["name"] == codex_market["name"] == "finos-mcp"
    assert claude_market["plugins"][0]["source"] == "./plugins/finos-mcp"
    assert codex_market["plugins"][0]["source"]["path"] == "./plugins/finos-mcp"
    assert claude_market["plugins"][0]["name"] == "finos-mcp"
    assert codex_market["plugins"][0]["name"] == "finos-mcp"

    project = tomllib.loads((PLUGIN / "pyproject.toml").read_text())
    assert set(project["project"]["dependencies"]) == {f"{p}=={PIN}" for p in PACKAGES.values()}
    assert "sources" not in project.get("tool", {}).get("uv", {})
    lock = tomllib.loads((PLUGIN / "uv.lock").read_text())
    for pkg in lock["package"]:
        if pkg["name"] == project["project"]["name"]:
            continue
        assert pkg["source"] == {"registry": "https://pypi.org/simple"}, pkg["name"]
        artifacts = pkg.get("wheels", []) + ([pkg["sdist"]] if "sdist" in pkg else [])
        assert artifacts and all(a["hash"].startswith("sha256:") for a in artifacts)
    files = []
    for directory, dirs, names in os.walk(PLUGIN):
        dirs[:] = [d for d in dirs if d not in (".venv", "__pycache__")]
        files.extend(Path(directory) / name for name in names)
    assert len(files) <= 512
    assert all(f.stat().st_size < 256 * 1024 for f in files)
    icon = (PLUGIN / ".claude-plugin" / "icon.png").read_bytes()
    assert icon[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", icon[16:24])
    assert width == height and 512 <= width <= 2048 and len(icon) < 2 * 1024 * 1024
    print("OK: plugin manifests, marketplaces, skills and pinned MCP servers")


if __name__ == "__main__":
    main()
