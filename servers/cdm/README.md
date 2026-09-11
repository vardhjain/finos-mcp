# finos-mcp-cdm

A read-only [MCP](https://modelcontextprotocol.io) server for the FINOS [Common Domain Model](https://cdm.finos.org/): type descriptions, the product and payout catalogue, event qualification, and validation of CDM JSON objects in both Rune (CDM 7) and legacy (CDM 6) formats, with every issue reported at its path in your document.

**Not affiliated with or endorsed by FINOS.** This is an independent, community package. On PyPI the `finos-` prefix is also used by official FINOS packages such as `finos-cdm`; this is not one of them.

## Run it

Requires Python 3.12+.

```bash
uvx --python 3.12 finos-mcp-cdm                                   # stdio
uvx --python 3.12 finos-mcp-cdm --transport streamable-http --port 8000
```

Claude Code: `claude mcp add finos-cdm -- uvx --python 3.12 finos-mcp-cdm`. Claude Desktop:

```json
{"mcpServers": {"finos-cdm": {"command": "uvx", "args": ["--python", "3.12", "finos-mcp-cdm"]}}}
```

## Tools

- `validate_object`: detects Rune or legacy format; each issue carries a JSON path and a kind.
- `describe_type`, `list_types`, `search_types`: fields, cardinality, choices and back-references.
- `list_products`, `explain_event`: payout catalogue and `Qualify_*` rules.
- `list_samples`, `get_sample`, `server_info`.

Full argument reference: <https://vardhjain.github.io/finos-mcp/tools/>.

## Safety

Read-only by construction: every tool is registered with `readOnlyHint: true` and the server refuses to serve tools otherwise. Content is vendored into the package with recorded upstream commit hashes, so the server makes no network calls at runtime. Every call is rate-limited, input-capped, audited as one JSON line, and fails with a structured error the agent can act on. Details: [finos-mcp-core](https://pypi.org/project/finos-mcp-core/).

Docs: <https://vardhjain.github.io/finos-mcp/> · Source: <https://github.com/vardhjain/finos-mcp> · Changelog: <https://github.com/vardhjain/finos-mcp/blob/main/CHANGELOG.md>

## Licence

Code is Apache-2.0. Vendored CDM materials are under the Community Specification License 1.0.
