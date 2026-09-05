# Changelog

## Unreleased

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
