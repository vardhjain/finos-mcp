# finos-mcp

Typed, **read-only** [MCP](https://modelcontextprotocol.io) servers for three FINOS data
standards, so an agent can query them without being able to change anything.

| Server | What it exposes | Official MCP Registry (v0.3.2) |
|---|---|---|
| `finos-mcp-aigf` (AI Governance Framework) | 24 risks, 25 controls, traceable references and crosswalks | [AIGF listing](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.vardhjain%2Ffinos-mcp-aigf/versions/0.3.2) |
| `finos-mcp-cdm` (Common Domain Model) | 767 CDM types, 1,143 JSON schemas, Rune/legacy trade validation | [CDM listing](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.vardhjain%2Ffinos-mcp-cdm/versions/0.3.2) |
| `finos-mcp-fdc3` (FDC3) | 19 standard intents, 28 context types and intent suggestions | [FDC3 listing](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.vardhjain%2Ffinos-mcp-fdc3/versions/0.3.2) |

These are **three independent local stdio servers**, not hosted remote
endpoints. All packages are released at **v0.3.2** and require Python 3.12+.

## Pick a question to try

| Your task | Start here |
|---|---|
| Find an AI risk or control with a citable identifier | [AIGF example](use-cases.md#1-map-an-ai-governance-control) |
| Inspect a `TradeState` field or schema | [CDM example](use-cases.md#2-understand-a-cdm-trade-type) |
| Suggest a standard desktop action for an instrument | [FDC3 example](use-cases.md#3-find-an-fdc3-action-for-a-selected-instrument) |

The [example recipes](use-cases.md) run real tools locally with **no paid
model API or API key**. To connect them to Claude, VS Code, or Copilot, use the
[MCP client setup guide](getting-started.md).

## Start here

- **[Safety model](safety.md)** — what "read-only" is enforced to mean, and the rate limits,
  size caps, structured errors and audit log that back it.
- **[Tool reference](tools.md)** — every tool, generated from the running servers.
- **[Demo transcript](demo.md)** — five real tool calls, including CDM catching three planted
  defects in a Rune-format `BusinessEvent`.

## Connect an assistant

Install [uv](https://docs.astral.sh/uv/) and choose the **one server** you
need. In [Claude Code](https://code.claude.com/docs/en/mcp), run one line:

```bash
claude mcp add --scope user finos-aigf -- uvx --python 3.12 finos-mcp-aigf==0.3.2
claude mcp add --scope user finos-cdm -- uvx --python 3.12 finos-mcp-cdm==0.3.2
claude mcp add --scope user finos-fdc3 -- uvx --python 3.12 finos-mcp-fdc3==0.3.2
```

Then run `claude mcp list` and ask the assistant to call a tool:
`get_control` for `mi-20` returns `AIR-PREV-020`;
`describe_type` for `TradeState` returns its schema details; and
`suggest_intent` with an `fdc3.instrument` and a price-chart goal
returns `ViewChart`. These were verified with real MCP stdio
connections against the published packages in the
[clean PyPI client tests](https://github.com/vardhjain/finos-mcp/actions/workflows/verify-public-pypi.yml).

For **Claude Desktop, VS Code and Copilot**, use the
[version-pinned JSON examples and setup instructions](getting-started.md).
The standard packages run locally and require no API key or paid model service
(the assistant/client itself may have separate access requirements).

To check installation **without an MCP client**, run
`uvx --python 3.12 finos-mcp-aigf==0.3.2 --help`. Running a stdio
server without `--help` simply waits for an MCP client connection.

A self-hosted Docker/HTTP alternative is explained in the
[repository README](https://github.com/vardhjain/finos-mcp#quick-start).
There is no project-operated public endpoint.

## What makes it trustworthy

Every standard is **vendored into the package** with its upstream commit hash and a per-file
sha256 manifest, verified at server start, so the servers make no network calls at runtime and
you can prove which revision an answer came from.

The claims are measured rather than asserted: CI publishes counts, test results, retrieval
recall and p95 tool latency to a [metrics branch](https://github.com/vardhjain/finos-mcp/tree/metrics)
on every push. Optional agent evaluations require an explicit manual approval of
paid API calls, and their last published results may be stale. The badges read
the published measurements.

Vendoring the standards also surfaced defects in them, which are written up in
**[upstream findings](upstream-findings.md)**. The first was fixed upstream on October 21, 2026: [issue #378](https://github.com/finos/ai-governance-framework/issues/378) and merged [PR #380](https://github.com/finos/ai-governance-framework/pull/380).
