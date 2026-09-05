# Contributing

Thanks for helping make FINOS standards easier for agents to use safely.

## Ground rules

- **Read-only stays read-only.** Pull requests that add a tool with side effects on any
  external system will not be merged; there is no configuration flag to allow it.
- **Vendored content is never edited by hand.** Run the server's `scripts/sync_upstream.py`
  and commit the result together with the regenerated `SOURCE.json`. If upstream content is
  wrong, fix it upstream (see [docs/upstream-findings.md](docs/upstream-findings.md)) and
  resync.
- **Every tool is typed.** One Pydantic input model per tool, a Pydantic return type, and a
  structured error for every anticipated failure.
- **Tests before merge.** `uv run pytest` must pass, `ruff check .`, `ruff format --check .`
  and `mypy` must be clean. Add a golden case under `evals/golden/<server>/` for any new tool.

## Setup

```bash
uv sync --all-packages
uv run pytest
```

The semantic-search extra (`uv sync --all-packages --extra semantic`) downloads a 15 MB open
model on first use; it is optional.

## Layout

| Path | What lives there |
|---|---|
| `core/` | `finos-mcp-core`: safety middleware, catalog search, schema registry, provenance |
| `servers/<name>/` | One package per standard: `models.py`, `parser.py`/`registry.py`, `server.py`, `_vendor/` |
| `evals/` | golden cases, retrieval set, agent-in-the-loop harness, latency benchmark, metrics |

## Commit messages

Conventional-ish: `feat(cdm): ...`, `fix(core): ...`, `chore(vendor): ...`. Explain the why.
