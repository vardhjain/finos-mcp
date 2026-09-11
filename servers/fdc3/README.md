# finos-mcp-fdc3

A read-only [MCP](https://modelcontextprotocol.io) server for [FDC3](https://fdc3.finos.org/): the standard intents, context-type schemas, context validation, and intent suggestion for a given context.

**Not affiliated with or endorsed by FINOS.** This is an independent, community package. On PyPI the `finos-` prefix is also used by official FINOS packages such as `finos-cdm`; this is not one of them.

## Run it

Requires Python 3.12+.

```bash
uvx --python 3.12 finos-mcp-fdc3                                   # stdio
uvx --python 3.12 finos-mcp-fdc3 --transport streamable-http --port 8000
```

Claude Code: `claude mcp add finos-fdc3 -- uvx --python 3.12 finos-mcp-fdc3`. Claude Desktop:

```json
{"mcpServers": {"finos-fdc3": {"command": "uvx", "args": ["--python", "3.12", "finos-mcp-fdc3"]}}}
```

## Tools

- `list_intents`, `get_intent`, `search_intents`, `find_intents_by_context`.
- `list_context_types`, `get_context_schema`, `validate_context`: issues carry a JSON path and a kind.
- `suggest_intent`: from a context object or type, optionally re-ranked by a goal.
- `server_info`.

Full argument reference: <https://vardhjain.github.io/finos-mcp/tools/>.

## Safety

Read-only by construction: every tool is registered with `readOnlyHint: true` and the server refuses to serve tools otherwise. Content is vendored into the package with recorded upstream commit hashes, so the server makes no network calls at runtime. Every call is rate-limited, input-capped, audited as one JSON line, and fails with a structured error the agent can act on. Details: [finos-mcp-core](https://pypi.org/project/finos-mcp-core/).

Docs: <https://vardhjain.github.io/finos-mcp/> · Source: <https://github.com/vardhjain/finos-mcp> · Changelog: <https://github.com/vardhjain/finos-mcp/blob/main/CHANGELOG.md>

## Licence

Code is Apache-2.0. Vendored FDC3 materials are under the Community Specification License 1.0.
