# finos-mcp-core

The shared safety layer for the finos-mcp servers
([`finos-mcp-aigf`](https://pypi.org/project/finos-mcp-aigf/),
[`finos-mcp-cdm`](https://pypi.org/project/finos-mcp-cdm/),
[`finos-mcp-fdc3`](https://pypi.org/project/finos-mcp-fdc3/)): read-only
[MCP](https://modelcontextprotocol.io) servers for FINOS data standards. You normally get it as
a dependency of one of those rather than installing it directly.

**Not affiliated with or endorsed by FINOS.** This is an independent, community package. On PyPI the `finos-` prefix is also used by official FINOS packages such as `finos-cdm`; this is not one of them.

## What it enforces

- **Read-only, no override.** A tool can only be registered with `readOnlyHint: true`; the server refuses to serve `tools/*` if any tool lacks it.
- **Rate limits.** Token bucket per client and tool; exhaustion is a JSON-RPC error (`-32029`, `rate_limited`) with `retry_after_s`.
- **Size caps.** Oversized arguments are rejected before the tool runs (`input_too_large`); oversized results are replaced with `output_too_large`.
- **Structured errors.** `not_found`, `ambiguous_id` (with candidates), `invalid_input`, `validation_failed`, `unsupported_format`.
- **Audit log.** One JSON line per request to stderr or `FINOS_MCP_AUDIT_PATH`, with a sha256 of the arguments rather than the arguments themselves.

Policy can only be tightened from the environment (`FINOS_MCP_MAX_INPUT_BYTES`,
`FINOS_MCP_RATE_CALLS`, `FINOS_MCP_RATE_WINDOW_S`, `FINOS_MCP_RATE_BURST`). The `semantic`
extra adds hybrid BM25 + static-embedding search; without it, nothing makes a network call.

Docs: <https://vardhjain.github.io/finos-mcp/> · Source: <https://github.com/vardhjain/finos-mcp> · Changelog: <https://github.com/vardhjain/finos-mcp/blob/main/CHANGELOG.md>

## Licence

Code is Apache-2.0.
