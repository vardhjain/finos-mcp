# Connect FINOS MCP to your AI assistant

These instructions install the independently maintained **read-only** FINOS MCP servers
for AIGF, CDM 7.8.0 and FDC3 from the published Python packages. No FINOS-specific
account, API key, paid model API or database is needed to run the servers.

Choose **one** server to begin with; running all three at the same time can use more memory.

## Prerequisites

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) so the `uvx`
   command is available to your MCP client. In a terminal, check `uvx --version`.
2. Have Python 3.12 available, or let uv install and manage it. Verify with
   `uv python install 3.12` and `uv python find 3.12`.
3. Install or open an MCP client that supports **local stdio** servers. The first `uvx`
   invocation downloads packages from PyPI; the installed standards data are vendored,
   so **the servers themselves require no network access at runtime**.

All examples intentionally pin the **published v0.3.1** packages so the setup is
repeatable. For newer versions, edit each `==0.3.1` pin after that release is published
and verified. Do not use the workspace's unpublished source version as a PyPI pin.

## Claude Desktop

Copy the complete [Claude Desktop JSON example](../examples/claude_desktop_config.json)
into your own `claude_desktop_config.json`, merging its `mcpServers` entries with
any servers you already have. Do not replace an existing config blindly.

- **Windows:** `%APPDATA%\\Claude\\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json` if your installation supports
  local MCP configuration (or `$XDG_CONFIG_HOME/Claude/claude_desktop_config.json`).

The example enables three separate stdio servers. To conserve memory, remove the
servers you do not need; one `finos-aigf` entry is enough to start. Save the JSON
and **restart Claude Desktop**. Confirm the local server appears in the available
tools/connectors, then use the verification prompt below.

Claude Desktop also supports desktop extensions; these JSON instructions are for
**manually configured local stdio** servers, not remote claude.ai connectors.

## Claude Code

In a shell with the `claude` command installed, run whichever lines you need:

```bash
claude mcp add --scope user finos-aigf -- uvx --python 3.12 finos-mcp-aigf==0.3.1
claude mcp add --scope user finos-cdm -- uvx --python 3.12 finos-mcp-cdm==0.3.1
claude mcp add --scope user finos-fdc3 -- uvx --python 3.12 finos-mcp-fdc3==0.3.1
```

`--scope user` makes each available in all your Claude Code projects. To share a
configuration only with one trusted project, instead copy the
[Claude Desktop JSON example](../examples/claude_desktop_config.json) as
`.mcp.json` in that project's root (Claude Code uses the same `mcpServers` shape),
and approve the project's server configuration when prompted.

Run `claude mcp list` in the shell and use `/mcp` inside Claude Code to check
connection status.

Official reference: [Claude Code MCP guide](https://code.claude.com/docs/en/mcp).

## VS Code

For the VS Code local MCP configuration format, copy the complete
[VS Code JSON example](../examples/vscode_mcp.json) into a **trusted**
workspace's `.vscode/mcp.json`, or add its entries to your user-level MCP
configuration. Unlike Claude Desktop, VS Code requires the top-level **`servers`**
key and `type: "stdio"` for command-based servers.

Use the Command Palette's **MCP: List Servers** action to start a server and
inspect its output. Review workspace trust and permissions before enabling any
third-party MCP server.

Official reference: [VS Code MCP configuration](https://code.visualstudio.com/docs/agents/reference/mcp-configuration).

## GitHub Copilot portable MCP configuration

If you use the **Copilot harness** or GitHub Copilot CLI, copy the
[portable Copilot JSON example](../examples/copilot_mcp.json) into the
workspace-root `.mcp.json` or your Copilot user config
(`~/.copilot/mcp-config.json`, unless `COPILOT_HOME` is set).
Portable files use **`mcpServers`**, not VS Code's `servers` format.
Review the MCP server trust settings before enabling it.

The portable `.mcp.json` file can be shared with your own team if the repository
is trusted. It is not the same format as `.vscode/mcp.json`.

Official reference: [VS Code / Copilot MCP format comparison](https://code.visualstudio.com/docs/agents/reference/mcp-configuration).

## Verify a real tool call

After connecting **AIGF**, ask your client:

> Use the finos-aigf MCP server's `get_control` tool to retrieve `mi-20`.
> Return its control id and the `aigf://` citation. Do not answer from memory.

You should see an actual `get_control` tool call with a result identifying
`AIR-PREV-020`. Confirm the response came from the MCP tool rather than
the assistant's own knowledge.

For the **CDM** server, ask for `describe_type` with name `TradeState`.
For **FDC3**, ask for `list_intents`. You can also try the
[demo walkthrough](demo.md).

## Troubleshooting

| Symptom | What to check |
|---|---|
| `uvx` not found | Run `uvx --version` in a normal terminal. Restart the desktop client after installing uv, or use the **full absolute path to uvx** in the `command` field (especially for GUI apps on macOS/Windows). |
| Python 3.12 not available | Run `uv python install 3.12`, then retry. The first setup needs network access to download Python and packages. |
| A server will not start | Test `uvx --python 3.12 'finos-mcp-aigf==0.3.1' --help` in a terminal; for the other servers, replace the package name. `--help` should exit without starting a persistent MCP session. |
| The server starts but no tool appears | Verify the client supports **stdio**, that the correct JSON wrapper was used, restart/reload the server, and inspect the client MCP server logs. |
| The configuration is rejected | Check JSON syntax and ensure you merged, not duplicated, the top-level `mcpServers` or `servers` key. |
| Startup is slow or uses too much RAM | Start only one of the three servers. CDM contains large, vendored standard definitions. |
| No call appears in the client | Explicitly request `get_control`, `describe_type` or `list_intents` and inspect the tool-call record. A plausible natural-language answer alone isn't proof. |

All FINOS MCP tools are read-only, but always review and trust the **client
configuration** before allowing it to launch local commands. The independent
packages are **not affiliated with or endorsed by FINOS**.
