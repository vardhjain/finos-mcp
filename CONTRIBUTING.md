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

## Recover a weekly vendor sync

The `vendor-check` workflow saves a `vendor-resync` artifact whenever upstream
content changes, before attempting to open a PR. It contains `base.txt`, a full
`vendor.patch` (including provenance files), and `stat.txt`. Artifacts expire after
14 days. A failed PR step still fails the run; inspect both its logs and the
parser/drift-test result before using the changes.

If the PR action pushed `chore/vendor-resync`, open a PR from that branch to
`main`. If no branch was pushed, download and extract the artifact, then from a
clean checkout run the following, replacing the paths with your extracted files:

```bash
git switch -c chore/vendor-resync-recovery <commit-from-base.txt>
git apply --check /path/to/vendor.patch
git apply --index /path/to/vendor.patch
uv sync --all-packages
uv run pytest servers/aigf/tests servers/cdm/tests/test_registry.py servers/fdc3/tests -rf
git diff --cached --stat
git commit -m "chore(vendor): recover upstream sync"
git push -u origin chore/vendor-resync-recovery
```

Open a PR to `main` and run the normal checks above before merging. If the logs
say GitHub Actions cannot create PRs, the owner can enable **Settings → Actions →
General → Workflow permissions → Allow GitHub Actions to create and approve pull
requests** and rerun the workflow. No additional token or paid service is needed.

## Commit messages

A short imperative summary line that says what changed and why, for example
`Fix the demo hang: await asyncio.sleep`. Automated vendor resyncs use `chore(vendor): ...`.

## Conduct and security

Everyone taking part is expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report
security problems privately, as described in [SECURITY.md](SECURITY.md).
