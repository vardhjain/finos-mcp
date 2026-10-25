# Using the servers

## Demo

[`demo_session.py`](demo_session.py) demonstrates **five real MCP calls** across AIGF, CDM
and FDC3. Each server runs in a **separate, short-lived Python process** and exits
before the next server starts. This avoids the previous demo-only out-of-memory
failure caused by holding all three registries and an embedding model at once.

```bash
uv sync --all-packages --all-extras
uv run --no-sync python examples/demo_session.py
uv run --no-sync python examples/demo_session.py --fast  # same output, no recording pauses
```

The output is produced by the **actual MCP client**, not a mock, and is checked
in CI on Ubuntu and Windows. A clean transcript from the Ubuntu CI run is also
uploaded as `demo-transcript.txt` in the GitHub Actions `metrics` artifact.
[`../docs/demo.md`](../docs/demo.md) shows the readable sample transcript.

To make an animated terminal recording, install the free
[VHS](https://github.com/charmbracelet/vhs) CLI (plus its terminal/font
requirements), then run:

```bash
vhs examples/demo.tape
```

This generates `docs/demo.gif`. Because each FINOS server is terminated between
segments, the recording no longer needs the memory to hold AIGF, both CDM schema
vintages, FDC3 and the search model simultaneously. GIF rendering still needs
VHS and a browser/terminal recorder; CI verifies the live text demo, not the
optional VHS installation.

## Claude Desktop

Merge [`claude_desktop_config.json`](claude_desktop_config.json) into your Claude Desktop config
(`%APPDATA%\Claude\claude_desktop_config.json` on Windows, `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS).
It uses `uvx`, so nothing has to be installed first; the first launch downloads the packages.

To run from a checkout instead, for development:

```json
{
  "mcpServers": {
    "finos-aigf": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/finos-mcp", "finos-mcp-aigf"]
    }
  }
}
```

Then ask, for example: *"Which AIGF controls mitigate prompt injection, and what do they map to in NIST SP 800-53? Cite the control ids."*

## Claude Code

```bash
claude mcp add finos-aigf -- uvx --python 3.12 finos-mcp-aigf
```

or, for a project-scoped `.mcp.json`:

```json
{
  "mcpServers": {
    "finos-aigf": { "command": "uvx", "args": ["--python", "3.12", "finos-mcp-aigf"] }
  }
}
```

## MCP Inspector

```bash
npx @modelcontextprotocol/inspector uv run --directory /path/to/finos-mcp finos-mcp-aigf
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
