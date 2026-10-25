# Three things you can do with FINOS MCP

FINOS MCP lets a local AI client consult financial-industry standards through
**read-only** tools instead of guessing what a schema field, governance control
or desktop intent means. Start with the problem you recognize.

The three examples below are real MCP tool calls, also tested automatically
in CI. They run from a local checkout and do **not** require an LLM, account,
paid inference, or a remote API. This is independent community software,
**not affiliated with or endorsed by FINOS**.

## Try a tool locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
git clone https://github.com/vardhjain/finos-mcp.git
cd finos-mcp
uv sync --all-packages
```

Pick just **one** command below. Each loads only the server needed for that
example and exits when finished; it does not hold all standards in memory
simultaneously. This is the source-checkout experience. To connect a
**published package** to your AI client instead, follow the
[MCP client setup guide](getting-started.md).

## 1. Map an AI governance control

You want to know which approved control covers an AI or MCP security risk.
AIGF exposes the published `AIR-*` identifiers, the risks mitigated by each
control, and references to other governance frameworks.

```bash
uv run --no-sync python examples/try_it.py aigf
```

The example calls **`get_control`** with `id=mi-20`. The result is checked for
**`AIR-PREV-020`**, and the script prints the tool's own citation URI.

Try this prompt in a connected MCP client:

> Use the AIGF `get_control` tool to retrieve `mi-20`. Explain what
> it mitigates, and cite the returned control identifier. Don't guess an ID.

**Use it for:** discovering documented controls and traceable governance
references, not deciding whether an organization is legally compliant.

## 2. Understand a CDM trade type

You need to generate or validate a trade document but aren't sure what
`TradeState` looks like. CDM 7.8.0 has vendored type descriptions and schemas
and supports validation of Rune and legacy CDM JSON formats.

```bash
uv run --no-sync python examples/try_it.py cdm
```

The example calls **`describe_type`** with `name=TradeState`, checks the
returned name and prints its **`cdm://` schema URI**. You can follow up
with `validate_object` for a real document; validation errors include JSON
paths. For an intentionally invalid Rune event, see the
[recorded demo](demo.md) (its transcript is an older CDM 7.7.0 snapshot).

Try this prompt in your MCP client:

> Use the CDM `describe_type` tool for `TradeState`. Show its fields,
> cardinalities and the schema resource I can cite.

**Use it for:** understanding schema structure and inspecting your generated
documents without sending trade data to a hosted validation API.

## 3. Find an FDC3 action for a selected instrument

Your finance app has a selected instrument and you want to know which
standard intent can show a price chart. The FDC3 server suggests intents
for context objects instead of inventing action names.

```bash
uv run --no-sync python examples/try_it.py fdc3
```

The example calls **`suggest_intent`** with an `fdc3.instrument` context,
ticker `AAPL` and goal `show a price chart`. The top suggestion is checked
as **`ViewChart`**.

Try this prompt in a connected MCP client:

> Use FDC3 `suggest_intent` for a context with type `fdc3.instrument`
> and ticker `AAPL`. My goal is to show a price chart. What standard
> intent is most appropriate?

**Use it for:** discovering interoperable desktop intent names and
context requirements. The tool *suggests* actions; it doesn't launch apps
or execute trades.

## From examples to a real integration

The example inputs are in
[examples/try_it_cases.json](https://github.com/vardhjain/finos-mcp/blob/main/examples/try_it_cases.json).
The executable script is
[examples/try_it.py](https://github.com/vardhjain/finos-mcp/blob/main/examples/try_it.py).
The regression tests invoke all three recipes through the actual local
MCP client on CI.

For Claude Desktop, Claude Code, VS Code or Copilot, copy the
[version-pinned client configurations](getting-started.md); the published
v0.3.1 distributions were independently tested on Python 3.12 and 3.14.

See the [full tool reference](tools.md), [safety model](safety.md),
and [detailed demo](demo.md) for more.
