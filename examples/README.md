# Using the servers

## Claude Desktop

Merge [`claude_desktop_config.json`](claude_desktop_config.json) into your Claude Desktop config
(`%APPDATA%\Claude\claude_desktop_config.json` on Windows, `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS).
It uses `uvx`, so nothing has to be installed first; the first launch downloads the packages.

Until the packages are on PyPI, point at this checkout instead:

```json
{
  "mcpServers": {
    "finos-aigf": {
      "command": "uv",
      "args": ["run", "--directory", "E:/Projects/FINOS_Project", "finos-mcp-aigf"]
    }
  }
}
```

Then ask, for example: *"Which AIGF controls mitigate prompt injection, and what do they map to in NIST SP 800-53? Cite the control ids."*

## Claude Code

```bash
claude mcp add finos-aigf -- uvx finos-mcp-aigf
```

or, for a project-scoped `.mcp.json`:

```json
{
  "mcpServers": {
    "finos-aigf": { "command": "uvx", "args": ["finos-mcp-aigf"] }
  }
}
```

## MCP Inspector

```bash
npx @modelcontextprotocol/inspector uv run --directory E:/Projects/FINOS_Project finos-mcp-aigf
```

Open the Tools tab: every tool shows an input schema and an output schema, and every result
arrives as `structuredContent`. Try `get_control` with `{"id": "mi-20"}` and then read the
`aigf://control/AIR-PREV-020` resource to see the citable source text.

## Streamable HTTP

```bash
uv run finos-mcp-aigf --transport streamable-http --host 127.0.0.1 --port 8000
```

The rate limiter keys on the `Mcp-Session-Id` header (falling back to the client address).
Set `FINOS_MCP_AUDIT_PATH=/var/log/finos-mcp/aigf.jsonl` to keep the audit log out of stderr.
