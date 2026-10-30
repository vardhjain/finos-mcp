# finos-mcp

**Lets AI assistants look things up in three open financial-industry standards, accurately and without being able to change anything.**

[![ci](https://github.com/vardhjain/finos-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/vardhjain/finos-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/finos-mcp-aigf?label=PyPI&color=0f7a68)](https://pypi.org/project/finos-mcp-aigf/)
[![Python](https://img.shields.io/pypi/pyversions/finos-mcp-aigf?color=0f7a68)](https://pypi.org/project/finos-mcp-aigf/)
[![License](https://img.shields.io/badge/license-Apache--2.0-0f7a68)](LICENSE)
[![tests](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fvardhjain%2Ffinos-mcp%2Fmetrics%2Fmetrics.json&query=%24.tests.passed&label=tests%20passing&color=0f7a68)](https://raw.githubusercontent.com/vardhjain/finos-mcp/metrics/metrics.json)
[![coverage](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fvardhjain%2Ffinos-mcp%2Fmetrics%2Fmetrics.json&query=%24.tests.coverage_pct&suffix=%25&label=coverage&color=0f7a68)](https://raw.githubusercontent.com/vardhjain/finos-mcp/metrics/metrics.json)
[![tools](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fvardhjain%2Ffinos-mcp%2Fmetrics%2Fmetrics.json&query=%24.exposure.tools_total&label=tools&color=0f7a68)](docs/tools.md)
[![recall@5](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fvardhjain%2Ffinos-mcp%2Fmetrics%2Fmetrics.json&query=%24.retrieval.recall_at_5&label=retrieval%20recall%405&color=0f7a68)](evals/retrieval)
[![hallucinated ids](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fvardhjain%2Ffinos-mcp%2Fmetrics%2Fmetrics-agent.json&query=%24.agent.hallucinated_id_rate&label=agent%20hallucinated%20ids&color=0f7a68)](evals/agent)

## Start with a question

| What you want to do | Pick this server | See it work |
|---|---|---|
| Find AI governance risks and controls with traceable references | **AIGF** | [Governance example](docs/use-cases.md#1-map-an-ai-governance-control) |
| Understand a trade field or validate CDM JSON | **CDM** | [CDM example](docs/use-cases.md#2-understand-a-cdm-trade-type) |
| Find the right desktop intent for a financial instrument | **FDC3** | [FDC3 example](docs/use-cases.md#3-find-an-fdc3-action-for-a-selected-instrument) |

**Official MCP Registry (published v0.3.2):**
[AIGF](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.vardhjain%2Ffinos-mcp-aigf/versions/0.3.2) ·
[CDM](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.vardhjain%2Ffinos-mcp-cdm/versions/0.3.2) ·
[FDC3](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.vardhjain%2Ffinos-mcp-fdc3/versions/0.3.2).
All three are **local stdio** packages, not public hosted endpoints.

**Claude Code and Codex plugins:** A community-maintained plugin can bundle all three
servers and their guided AIGF, CDM, and FDC3 skills. See the
[plugin installation guide](docs/plugins.md) for marketplace setup and local
runtime requirements; the existing manual MCP commands below still work.

**Claude Code quick connect:** With [Claude Code](https://code.claude.com/docs/en/mcp)
and [uv](https://docs.astral.sh/uv/) installed, run **one** of the following
commands for the standard you need:

```bash
claude mcp add --scope user finos-aigf -- uvx --python 3.12 finos-mcp-aigf==0.3.2
claude mcp add --scope user finos-cdm -- uvx --python 3.12 finos-mcp-cdm==0.3.2
claude mcp add --scope user finos-fdc3 -- uvx --python 3.12 finos-mcp-fdc3==0.3.2
```

Run `claude mcp list` and then ask your assistant to use `get_control`
(AIGF), `describe_type` (CDM), or `suggest_intent` (FDC3).
The [client setup guide](docs/getting-started.md) also provides tested
JSON configuration examples for **Claude Desktop, VS Code and Copilot**,
with troubleshooting for Windows and macOS.

To **see a real MCP call without a model or API key**, clone this repository,
run `uv sync --all-packages`, then try:

```bash
uv run --no-sync python examples/try_it.py aigf
```

Choose either of the other two servers in the [tested example recipes](docs/use-cases.md).
This is independent community software, not an official FINOS product.

## What is this?

Banks and other financial firms share a set of open standards published by
[FINOS](https://www.finos.org/), the Fintech Open Source Foundation. Three of them matter here:

- the **AI Governance Framework**, a catalogue of the risks of using AI in finance and the
  controls that reduce them;
- the **Common Domain Model (CDM)**, a shared way to describe trades and what happens to them;
- **FDC3**, the standard that lets desktop finance applications talk to each other.

An AI assistant asked about these standards will often answer from memory and get details
wrong: an id that does not exist, a field that is not in the schema. This project gives the
assistant the real thing to look up instead. It packages each standard as a small server that
speaks the [Model Context Protocol](https://modelcontextprotocol.io) (MCP), the open protocol
that Claude and other assistants use to call external tools.

With the servers connected, an assistant can answer questions like:

- *"Which controls reduce the risk of prompt injection, and what do they map to in the EU AI Act?"*
- *"Is this trade JSON valid CDM? If not, where exactly is it wrong?"*
- *"My app has a stock ticker selected. Which FDC3 actions can I offer the user?"*

Each answer comes with an identifier or link the reader can check against the standard itself.

## The three servers

| Server | Standard | What an assistant can do with it |
|---|---|---|
| `finos-mcp-aigf` | [AI Governance Framework](https://air-governance-framework.finos.org/) | Look up 24 risks and 25 controls by their published ids, see which controls address which risks, cross-reference 13 outside frameworks (NIST, ISO 42001, EU AI Act, OWASP), and search in plain language |
| `finos-mcp-cdm` | [Common Domain Model](https://cdm.finos.org/) | Explore 767 CDM types and 1,143 JSON schemas, browse products and trade events, and validate trade documents with exact error paths |
| `finos-mcp-fdc3` | [FDC3](https://fdc3.finos.org/) | Look up 19 standard actions ("intents") and 28 data types, check a data object, and suggest which actions fit it |

All three are built on [`finos-mcp-core`](core/), a shared package that holds the safety rules
described below. The full list of 29 tools is in [docs/tools.md](docs/tools.md), and
[docs/demo.md](docs/demo.md) shows a real session, including the CDM server finding three
deliberate mistakes in a trade document.

## Quick start

You need [uv](https://docs.astral.sh/uv/) and nothing else. There is no account, API key or
database to set up.

**First-time setup:** Follow the [MCP client setup guide](docs/getting-started.md) for
copy-paste, version-pinned configurations for Claude Desktop, Claude Code,
VS Code and GitHub Copilot. It also covers Windows and macOS setup, verifying
a real tool call, and troubleshooting. The quick-start examples below pin
the **published, end-to-end-tested v0.3.2** packages.

**Claude Desktop or Claude Code.** Add this to your MCP configuration
([full example](examples/claude_desktop_config.json)) and restart:

```json
{
  "mcpServers": {
    "finos-aigf": { "command": "uvx", "args": ["--python", "3.12", "finos-mcp-aigf==0.3.2"] }
  }
}
```

**From the command line.**

```bash
# talk over stdin/stdout, the way desktop assistants connect
uvx --python 3.12 finos-mcp-aigf==0.3.2

# or serve HTTP on localhost (self-hosted, not a public hosted service)
uvx --python 3.12 finos-mcp-aigf==0.3.2 --transport streamable-http --port 8000
```

**As a container.** It needs no writable disk and no extra privileges:

```bash
docker run --rm -p 8000:8000 --read-only --cap-drop ALL \
  -e FINOS_MCP_ALLOWED_HOSTS='localhost:*,127.0.0.1:*' \
  ghcr.io/vardhjain/finos-mcp:v0.3.2
```

The allowed-hosts setting makes the server refuse requests that arrive under any other host
name, which stops a web page in your browser from reaching the port.

Running a stdio command directly **starts a server waiting for a client**;
it does not display a chat prompt. To verify installation in a terminal,
add `--help` instead. Swap `finos-mcp-aigf` for `finos-mcp-cdm` or
`finos-mcp-fdc3` to run the other servers.
[examples/](examples/) includes a [low-memory, reproducible live demo](examples/README.md),
a short Python client, and a LangGraph agent.

## Why it is safe to connect

Giving an assistant new tools is a risk, so the servers are deliberately limited:

- **They can only read.** No tool writes a file, sends a message or changes any system. The
  server refuses to serve any tool if one of them is not marked read-only.
- **They work offline.** The standards are copied into the packages at build time, with the
  exact upstream version recorded. Nothing is fetched while the server runs.
- **They cannot be flooded.** Every tool has a rate limit and a cap on input and output size.
- **Mistakes are explained.** A bad request gets a structured error that says what was wrong
  and what to try, so the assistant can correct itself instead of guessing.
- **Everything is logged.** Each call is written to an audit log, with a fingerprint of its
  arguments in place of the raw content.

The details, including every setting, are in [docs/safety.md](docs/safety.md).

One optional feature does use the network. Installing the `semantic` extra adds
meaning-based search, which downloads a small open model on first use. Without it, search is
keyword-based and fully offline.

## How well it works

These numbers are measured by automated checks and published to the
[`metrics`](https://github.com/vardhjain/finos-mcp/tree/metrics) branch. The badges above read
that file directly, so they show measurements from a specific commit.

| Check | Result |
|---|---|
| Automated tests | Over 200 passing, with more than 90% of the code exercised. The exact figures are on the badges above |
| Finding the right record for a plain-language question (50 questions) | Correct answer in the top five 91.5% of the time |
| An AI model answering 20 governance questions through the server | 0 invented ids; 95% of answers cited a valid id |
| Response time per tool call | A few milliseconds on the benchmarked tools |

The offline metrics update on every push to `main`; the search result in this
table is from October 2026. The agent test uses Claude Haiku 4.5 and requires paid
Anthropic API credits. To prevent surprise costs, it only runs through an explicit
manual opt-in in GitHub Actions, never on a timer or PR label. Its published figures
are from the last successful evaluation on 14 September 2026 and are not live data.
Deterministic tests and retrieval evaluations continue to run in CI without LLM API calls.

Building this also turned up 15 defects in the upstream standards, recorded in
[docs/upstream-findings.md](docs/upstream-findings.md). The first was reported to FINOS, and its YAML fix merged upstream
in PR #380 on October 21, 2026.

## Project layout

| Path | Contents |
|---|---|
| [`core/`](core/) | Shared safety layer: read-only enforcement, rate limits, size caps, audit log, search |
| [`servers/`](servers/) | One package per standard, each with its copy of the upstream content |
| [`evals/`](evals/) | Golden tests, AIGF retrieval, [offline CDM/FDC3 workflows](evals/offline/), latency and optional agent evaluation |
| [`examples/`](examples/) | Configuration and sample clients |
| [`docs/`](docs/) | Documentation, also published at <https://vardhjain.github.io/finos-mcp/> |

## Development

```bash
uv sync --all-packages --all-extras
uv run pytest
uv run pytest evals/offline/test_workflows.py -v  # 16 multi-tool scenarios, no paid APIs
uv run ruff check . && uv run mypy core/src servers/*/src
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the ground rules, [CHANGELOG.md](CHANGELOG.md) for
what changed in each release, [RELEASING.md](RELEASING.md) for how releases are made, and
[PLAN.md](PLAN.md) for the original design record.

## Status

For maintainers, [MCP directory and Registry status](docs/directory-listings.md)
records the three already-published official Registry entries and the pending
Glama listing correction. Future third-party directory submissions require
separate approval.

The [latest published release](https://github.com/vardhjain/finos-mcp/releases/latest) is available on
PyPI as [`finos-mcp-core`](https://pypi.org/project/finos-mcp-core/),
[`finos-mcp-aigf`](https://pypi.org/project/finos-mcp-aigf/),
[`finos-mcp-cdm`](https://pypi.org/project/finos-mcp-cdm/) and
[`finos-mcp-fdc3`](https://pypi.org/project/finos-mcp-fdc3/), for Python 3.12 and later, and as
a container image for x86 and ARM.

**Not affiliated with or endorsed by FINOS.** These are independent community packages. Some
official FINOS packages on PyPI also start with `finos-`; nothing here is one of them.

## Licenses

The code is Apache-2.0. The copied standards keep their own licenses: the AI Governance
Framework is CC-BY-4.0, and CDM and FDC3 are under the Community Specification License 1.0.
See [NOTICE](NOTICE).
