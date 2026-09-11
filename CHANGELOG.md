# Changelog

## 0.1.2 — 2026-09-11

Metadata-only release: no code or vendored content changed.

### Fixed
- The PyPI pages were close to blank: each package's long description was a single heading.
  Every package now has a real README with what it exposes, how to run it, the safety model,
  and a notice that it is **not affiliated with or endorsed by FINOS**.
- Added project URLs (docs, repository, changelog, issues), keywords, and summaries that name
  each standard instead of its short code.

## 0.1.1 — 2026-09-11

First release published to PyPI, all four packages at 0.1.1. `finos-mcp-core`, `-aigf` and
`-cdm` published with the tag; `finos-mcp-fdc3` followed by re-running only its publish job
in the same release, because PyPI allows at most three pending trusted publishers per account
(see RELEASING.md). All four share one version and one build.

### Added
- Streamable-HTTP transport covered by a test that spawns the real console script; it is the
  only transport where rate limits key on the `Mcp-Session-Id` header.
- Container image `ghcr.io/vardhjain/finos-mcp`, smoke-tested in CI by running it
  `--read-only --cap-drop ALL` and driving it with a real MCP client before any push.
- Documentation site at <https://vardhjain.github.io/finos-mcp/>, built with `--strict`.
- Nightly agent-eval metrics published to the `metrics` branch as `metrics-agent.json`.

### Changed
- The agent eval now separates hallucinated control ids (zero tolerance) from answers that
  cite no id at all, and its diagnostics upload even when a gate fails.
- PyPI publishing runs one matrix job per package, each in its own tag-restricted GitHub
  environment, with `PYPI_SKIP_PACKAGES` to hold a package back from a release.

### Fixed
- The LangGraph example: `langchain-mcp-adapters` requires MCP SDK 1.x, so it is no longer
  declared beside the 2.x servers and the example documents running it in its own environment.

## 0.1.0 — 2026-09-08

### Added
- `finos-mcp-core`: read-only tool enforcement, per-tool token-bucket rate limits, input and
  output size caps, structured `ErrorEnvelope` tool errors, JSONL audit log, in-process
  metrics, BM25 catalog search with Snowball stemming and optional static-embedding hybrid
  ranking, JSON Schema registry for draft-04 and 2019-09 sibling references, vendor
  provenance manifests.
- `finos-mcp-aigf`: FINOS AI Governance Framework at `finos/ai-governance-framework@7728f95`
  with public `AIR-*` ids, risk/control graph, crosswalks to 13 reference frameworks, search,
  reverse crosswalk lookup, `aigf://` resources and two prompts.
- `finos-mcp-cdm`: CDM 7.2.0 JSON Schema (1139 files) plus the 6.27.0 vintage (1066),
  type descriptions, product and payout catalogue, 35 event-qualification rules, 40 sample
  documents, and `validate_object` for both Rune (CDM 7) and legacy JSON via schema-directed
  normalisation.
- `finos-mcp-fdc3`: FDC3 2.2.3 context schemas (29), 19 intents with a generated
  intent-to-context table, context validation, intent suggestion, `fdc3://` resources.
- Evals: 46 golden cases, a 50-question AIGF retrieval set with recall@k and MRR, an
  agent-in-the-loop suite where Claude must cite valid control ids, a latency benchmark,
  and a metrics collector wired into GitHub Actions.
