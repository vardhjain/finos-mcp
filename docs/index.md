# finos-mcp

Typed, **read-only** [MCP](https://modelcontextprotocol.io) servers for three FINOS data
standards, so an agent can query them without being able to change anything.

| Server | Standard | What it exposes |
|---|---|---|
| `finos-mcp-aigf` | [AI Governance Framework](https://air-governance-framework.finos.org/) | 23 risks and 23 controls under their published `AIR-*` ids, the risk-to-control graph, crosswalks to 13 reference frameworks, search, citable resources |
| `finos-mcp-cdm` | [Common Domain Model](https://cdm.finos.org/) | 1139 schemas, 16 root types, 35 event-qualification rules, and validation of CDM JSON in both the Rune (CDM 7) and legacy shapes |
| `finos-mcp-fdc3` | [FDC3](https://fdc3.finos.org/) | 19 intents with a generated intent-to-context table, 28 context types, context validation and intent suggestion |

## Start here

- **[Safety model](safety.md)** — what "read-only" is enforced to mean, and the rate limits,
  size caps, structured errors and audit log that back it.
- **[Tool reference](tools.md)** — every tool, generated from the running servers.
- **[Demo transcript](demo.md)** — five real tool calls, including CDM catching three planted
  defects in a Rune-format `BusinessEvent`.

## Install

```bash
# Claude Desktop / Claude Code, no install step
uvx finos-mcp-aigf        # once published to PyPI

# from a checkout
uv run finos-mcp-aigf
```

Or over HTTP, in a container:

```bash
docker run --rm -p 8000:8000 --read-only --cap-drop ALL ghcr.io/vardhjain/finos-mcp
```

## What makes it trustworthy

Every standard is **vendored into the package** with its upstream commit hash and a per-file
sha256 manifest, verified at server start, so the servers make no network calls at runtime and
you can prove which revision an answer came from.

The claims are measured rather than asserted: CI publishes counts, test results, retrieval
recall and p95 tool latency to a [metrics branch](https://github.com/vardhjain/finos-mcp/tree/metrics)
on every push, and a nightly agent eval records whether a model citing these controls ever
invents an id. The badges on the repository read those files.

Vendoring the standards also surfaced defects in them, which are written up in
**[upstream findings](upstream-findings.md)**. The first has been reported back to FINOS as [issue #378](https://github.com/finos/ai-governance-framework/issues/378), with the fix in [PR #380](https://github.com/finos/ai-governance-framework/pull/380).
