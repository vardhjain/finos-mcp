# finos-mcp-aigf

A read-only [MCP](https://modelcontextprotocol.io) server for the FINOS [AI Governance Framework](https://air-governance-framework.finos.org/): its risks and controls with their public `AIR-*` ids, risk-to-control mapping, crosswalks to NIST SP 800-53, ISO 42001, the EU AI Act and OWASP, and full-text search with citable `aigf://` resources.

**Not affiliated with or endorsed by FINOS.** This is an independent, community package. On PyPI the `finos-` prefix is also used by official FINOS packages such as `finos-cdm`; this is not one of them.

## Run it

Requires Python 3.12+.

```bash
uvx --python 3.12 finos-mcp-aigf                                   # stdio
uvx --python 3.12 finos-mcp-aigf --transport streamable-http --port 8000
```

Claude Code: `claude mcp add finos-aigf -- uvx --python 3.12 finos-mcp-aigf`. Claude Desktop:

```json
{"mcpServers": {"finos-aigf": {"command": "uvx", "args": ["--python", "3.12", "finos-mcp-aigf"]}}}
```

## Tools

- `get_risk`, `get_control`, `list_risks`, `list_controls`: accept `AIR-SEC-010`, `ri-10`, `10` or a title.
- `map_risks_to_controls`: controls ranked by how many of the given risks they cover.
- `map_control_to_external`, `find_by_external_reference`, `list_reference_frameworks`: crosswalks in both directions.
- `search_framework`: BM25 search; install `finos-mcp-aigf[semantic]` for hybrid search (downloads a ~15 MB model on first use).
- `search_status`, `server_info`.

Full argument reference: <https://vardhjain.github.io/finos-mcp/tools/>.

## Safety

Read-only by construction: every tool is registered with `readOnlyHint: true` and the server refuses to serve tools otherwise. Content is vendored into the package with recorded upstream commit hashes, so the server makes no network calls at runtime. Every call is rate-limited, input-capped, audited as one JSON line, and fails with a structured error the agent can act on. Details: [finos-mcp-core](https://pypi.org/project/finos-mcp-core/).

Docs: <https://vardhjain.github.io/finos-mcp/> · Source: <https://github.com/vardhjain/finos-mcp> · Changelog: <https://github.com/vardhjain/finos-mcp/blob/main/CHANGELOG.md>

## Licence

Code is Apache-2.0. The vendored AI Governance Framework content is CC-BY-4.0.
