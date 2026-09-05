# finos-mcp

Typed, read-only [MCP](https://modelcontextprotocol.io) servers for FINOS data standards, so any agent can query them safely:

| Server | Standard | What it exposes |
|---|---|---|
| `finos-mcp-aigf` | [AI Governance Framework](https://air-governance-framework.finos.org/) | Risks and controls with their public `AIR-*` ids, risk-to-control mapping, crosswalks to NIST / ISO 42001 / EU AI Act / OWASP, full-text search, citable resources |
| `finos-mcp-cdm` | [Common Domain Model](https://cdm.finos.org/) | Type descriptions, product and payout catalogue, event qualification, and validation of CDM JSON objects (Rune and legacy formats) |
| `finos-mcp-fdc3` | [FDC3](https://fdc3.finos.org/) | Intents, context-type schemas, context validation, intent suggestion for a given context |

All three share [`finos-mcp-core`](core/), which is where the safety guarantees live.

## Safety model

**These servers are read-only.** They contain no tool that writes to, posts to, or mutates any external system, file, or network endpoint. All framework content and schemas are vendored into the packages at build time with recorded upstream commit hashes (`SOURCE.json` in each `_vendor/` directory); the servers make **no network calls at runtime**. Every tool call is rate-limited per tool, input-capped, and written to an audit log. Any failure is returned as a structured error the calling agent can act on.

Concretely, `finos-mcp-core` enforces:

- **Read-only, no override.** A tool can only be registered with `readOnlyHint: true`; the server refuses to serve `tools/*` if any tool lacks it.
- **Rate limits.** Token bucket per client and tool; exhaustion is a JSON-RPC error (`-32029`, `rate_limited`) with `retry_after_s`.
- **Size caps.** Serialised arguments above the cap (64 KiB by default; 1 MiB for CDM validation) are rejected before the tool runs with a structured `input_too_large` result; oversized results are replaced with `output_too_large` and a hint to narrow the request.
- **Structured errors.** `not_found`, `ambiguous_id` (with candidates), `invalid_input`, `validation_failed`, `unsupported_format`: JSON the model can parse and recover from.
- **Audit log.** One JSON line per request to stderr or `FINOS_MCP_AUDIT_PATH`, with the tool name, a sha256 of the arguments (never the raw arguments unless `FINOS_MCP_AUDIT_RAW_ARGS=1`), outcome and duration.

Policy can only be tightened from the environment (`FINOS_MCP_MAX_INPUT_BYTES`, `FINOS_MCP_RATE_CALLS`, `FINOS_MCP_RATE_WINDOW_S`, `FINOS_MCP_RATE_BURST`).

The default install is **lexical-only and makes no network calls**: `search_framework` is plain BM25 with a fuzzy title boost. Installing the optional `semantic` extra (`finos-mcp-core[semantic]` / `finos-mcp-aigf[semantic]`, pulling in `model2vec`) enables hybrid search — BM25 fused with a small (~15 MB, MIT-licensed) static-embedding model, `minishlab/potion-base-4M` by default — which downloads that model from Hugging Face on first use unless `FINOS_MCP_EMBEDDING_MODEL` points at a local copy. Loading the model never blocks correctness: any failure (extra not installed, no network, bad path) is caught and leaves the server in pure lexical mode. The active mode is visible via the `search_status` tool, and `FINOS_MCP_SEARCH_MODE=lexical` forces lexical-only explicitly regardless of what is installed.

## Status

Under active development. See [PLAN.md](PLAN.md) for the design, milestones and the metrics that CI publishes.

## Development

```bash
uv sync --all-packages --all-extras
uv run pytest
uv run ruff check . && uv run mypy core/src servers/*/src
```

## Licenses

Code is Apache-2.0. Vendored content keeps its upstream license: the AI Governance Framework is CC-BY-4.0; CDM and FDC3 materials are under the Community Specification License 1.0. See [NOTICE](NOTICE).
