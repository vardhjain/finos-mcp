# FINOS MCP (Community)

Independent, community-maintained reference tools for the FINOS AI Governance
Framework (AIGF), Common Domain Model (CDM), and FDC3. Not affiliated with or
endorsed by FINOS. Includes three guided skills and three read-only MCP servers.

## Requirements and installation

Install uv and Python 3.12 and make uv available on the client's PATH. In Claude Code:

```text
/plugin marketplace add vardhjain/finos-mcp
/plugin install finos-mcp@finos-mcp
```

Start a new session and check `/mcp`. Local servers work in Claude Code and
Cowork. They cannot run in claude.ai web chat. Claude Desktop chat can use
separately configured local MCP servers; see the repository's client setup guide.

The first launch downloads packages from public PyPI. The bundled pyproject.toml
and uv.lock pin the runtime and all transitive dependencies, including artifact
hashes. Launches use the plugin project with --frozen and --no-config,
so the repository's development workspace sources are not used. Normal reference
lookups then work offline. No FINOS API key, database or hosted endpoint is needed.
All three servers share a runtime environment; their processes consume memory separately.

## Try the tools

- AIGF: use get_control with id mi-20 and return its citation URI.
- CDM: use describe_type for TradeState and return its schema URI.
- FDC3: use suggest_intent with an fdc3.instrument context and goal "show a chart".

## Data handling

Tools read bundled public standards. User tool arguments are processed locally;
there are no model calls or runtime requests to FINOS services. Startup package
downloads contact PyPI. Servers emit local audit metadata to stderr, including
method/tool names, argument sizes and hashes; client logging and retention are
controlled by the client. Do not supply credentials or private trade data in tests.

Documentation: https://vardhjain.github.io/finos-mcp/
Support: https://github.com/vardhjain/finos-mcp/issues
License: Apache-2.0 (see LICENSE).
