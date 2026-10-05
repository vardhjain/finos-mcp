# finos-mcp

**Lets AI assistants look things up in three open financial-industry standards, accurately and without being able to change anything.**

[![ci](https://github.com/vardhjain/finos-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/vardhjain/finos-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/finos-mcp-aigf?label=PyPI&color=0f7a68)](https://pypi.org/project/finos-mcp-aigf/)
[![Python](https://img.shields.io/pypi/pyversions/finos-mcp-aigf?color=0f7a68)](https://pypi.org/project/finos-mcp-aigf/)
[![License](https://img.shields.io/badge/license-Apache--2.0-0f7a68)](LICENSE)
[![tests](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fvardhjain%2Ffinos-mcp%2Fmetrics%2Fmetrics.json&query=%24.tests.passed&label=tests%20passing&color=0f7a68)](https://raw.githubusercontent.com/vardhjain/finos-mcp/metrics/metrics.json)
[![tools](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fvardhjain%2Ffinos-mcp%2Fmetrics%2Fmetrics.json&query=%24.exposure.tools_total&label=tools&color=0f7a68)](docs/tools.md)
[![recall@5](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fvardhjain%2Ffinos-mcp%2Fmetrics%2Fmetrics.json&query=%24.retrieval.recall_at_5&label=retrieval%20recall%405&color=0f7a68)](evals/retrieval)
[![hallucinated ids](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fvardhjain%2Ffinos-mcp%2Fmetrics%2Fmetrics-agent.json&query=%24.agent.hallucinated_id_rate&label=agent%20hallucinated%20ids&color=0f7a68)](evals/agent)

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
| `finos-mcp-aigf` | [AI Governance Framework](https://air-governance-framework.finos.org/) | Look up 23 risks and 23 controls by their published ids, see which controls address which risks, cross-reference 13 outside frameworks (NIST, ISO 42001, EU AI Act, OWASP), and search in plain language |
| `finos-mcp-cdm` | [Common Domain Model](https://cdm.finos.org/) | Describe any of 1,142 data types, browse products and trade events, and check a trade document for errors, with the location of each one |
| `finos-mcp-fdc3` | [FDC3](https://fdc3.finos.org/) | Look up 19 standard actions ("intents") and 28 data types, check a data object, and suggest which actions fit it |

All three are built on [`finos-mcp-core`](core/), a shared package that holds the safety rules
described below. The full list of 29 tools is in [docs/tools.md](docs/tools.md), and
[docs/demo.md](docs/demo.md) shows a real session, including the CDM server finding three
deliberate mistakes in a trade document.

## Quick start

You need [uv](https://docs.astral.sh/uv/) and nothing else. There is no account, API key or
database to set up.

**Claude Desktop or Claude Code.** Add this to your MCP configuration
([full example](examples/claude_desktop_config.json)) and restart:

```json
{
  "mcpServers": {
    "finos-aigf": { "command": "uvx", "args": ["--python", "3.12", "finos-mcp-aigf"] }
  }
}
```

**From the command line.**

```bash
# talk over stdin/stdout, the way desktop assistants connect
uvx --python 3.12 finos-mcp-aigf

# or serve HTTP on localhost
uvx --python 3.12 finos-mcp-aigf --transport streamable-http --port 8000
```

**As a container.** It needs no writable disk and no extra privileges:

```bash
docker run --rm -p 8000:8000 --read-only --cap-drop ALL ghcr.io/vardhjain/finos-mcp
```

Swap `finos-mcp-aigf` for `finos-mcp-cdm` or `finos-mcp-fdc3` to run the other servers.
[examples/](examples/) has a short Python client and a LangGraph agent.

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
| Automated tests | 156 passing, 93.6% of the code exercised |
| Finding the right record for a plain-language question (50 questions) | Correct answer in the top five 91.5% of the time |
| An AI model answering 20 governance questions through the server | 0 invented ids; 95% of answers cited a valid id |
| Response time per tool call | A few milliseconds on the benchmarked tools |

Figures are from September 2026 runs. The model test uses Claude Haiku 4.5 and runs nightly.

Building this also turned up 15 defects in the upstream standards, recorded in
[docs/upstream-findings.md](docs/upstream-findings.md). The first has been reported to FINOS
with a proposed fix.

## Project layout

| Path | Contents |
|---|---|
| [`core/`](core/) | Shared safety layer: read-only enforcement, rate limits, size caps, audit log, search |
| [`servers/`](servers/) | One package per standard, each with its copy of the upstream content |
| [`evals/`](evals/) | The measurements above: reference answers, search quality, speed, and the AI model test |
| [`examples/`](examples/) | Configuration and sample clients |
| [`docs/`](docs/) | Documentation, also published at <https://vardhjain.github.io/finos-mcp/> |

## Development

```bash
uv sync --all-packages --all-extras
uv run pytest
uv run ruff check . && uv run mypy core/src servers/*/src
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the ground rules, [CHANGELOG.md](CHANGELOG.md) for
what changed in each release, [RELEASING.md](RELEASING.md) for how releases are made, and
[PLAN.md](PLAN.md) for the original design record.

## Status

Version [0.2.4](https://github.com/vardhjain/finos-mcp/releases/tag/v0.2.4) is released on
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
