# finos-mcp — Implementation Plan

Typed, read-only MCP servers for three FINOS standards (AIGF, CDM, FDC3), a shared safety core, and a measurable eval suite.

Date: 2026-09-04. All upstream facts below were verified against live sources on that date; links are inline. Decisions that deviate from the original brief are called out in §13.

---

## 0. One-paragraph pitch

`finos-mcp` is a Python 3.12 monorepo shipping three MCP servers that let any agent query FINOS data standards through typed tools: `finos-mcp-aigf` (AI Governance Framework risks and controls, with derived `AIR-SEC-010` style IDs and crosswalks to NIST/ISO/EU AI Act/OWASP), `finos-mcp-cdm` (Common Domain Model type descriptions and object validation, the "check your own output" tool), and `finos-mcp-fdc3` (intents, context schemas, context validation, intent suggestion). A shared `core` package enforces read-only tools, per-tool rate limits, input size caps, structured errors, and an audit log. Everything is vendored with provenance, so the servers run fully offline. An `evals` package proves it with golden schema tests, a 50-question retrieval set with recall@k, and an agent-in-the-loop test where Claude must answer with a cited control ID. CI logs verifiable metrics on every run.

---

## 1. Research findings that shape the design

### 1.1 AIGF (finos/ai-governance-framework)

| Fact | Detail | Source |
|---|---|---|
| Content location | `docs/_risks/` (23 files) and `docs/_mitigations/` (23 files), Jekyll collections. | [repo](https://github.com/finos/ai-governance-framework) |
| File naming | `ri-<seq>_<slug>.md`, `mi-<seq>_<slug>.md`. Cross-links use only `ri-N` / `mi-N`. | [CONVENTIONS.md](https://raw.githubusercontent.com/finos/ai-governance-framework/main/CONVENTIONS.md) |
| Public ID | Not in frontmatter. Derived at build time: `AIR-{type}-{seq:03d}`. Risk types `RC`, `OP`, `SEC`; mitigation types `PREV`, `DET`. So `mi-20` (PREV) is `AIR-PREV-020`. | `docs/_includes/risk-id.html`, `docs/_config.yml` |
| Frontmatter | `sequence`, `title`, `layout`, `doc-status`, `type`, `related_risks`, `mitigates` (mitigations only, one-way), `related_mitigations`, and any number of `<dataset>_references` lists. | `docs/_risks/ri-10_prompt-injection.md` |
| External crosswalks | 14 YAML datasets in `docs/_data/references/` (`nist-sp-800-53r5`, `nist-ai-600-1`, `iso-42001`, `eu-ai-act`, `owasp-llm`, `owasp-ml`, `owasp-asi`, `ffiec-itbooklets`, `iosco-supervisory-toolkit`, `sr11-7`, `atr`, `uk-regulations`, `canada-regulations`). Each `<name>_references` key resolves into `<name>.yml` `entries:`. | `docs/_data/references/` |
| Risk to mitigation link | One-way: only mitigations carry `mitigates:`. Risk-side list must be computed by inversion. | risk layout Liquid |
| YAML gotcha | Reference lists carry inline `# title` comments. Parser must tolerate comments. | `scripts/annotate_yaml_front_matter.py` |
| Versions | Tags `v1` (2025-06-20) and `v2` (2025-10-20). No GitHub Releases. `main` has post-v2 additions (`owasp-asi`, `atr`, UK/Canada). | [tags](https://github.com/finos/ai-governance-framework/tags) |
| License | CC-BY-4.0 (content). | `LICENSE.spdx` |
| Existing MCP server | `finos/aigf-mcp-server` (Citi-led, FastMCP 2.x, Python ≥3.10). 11 tools: `list_frameworks`, `get_framework`, `search_frameworks`, `list_risks`, `get_risk`, `search_risks`, `list_mitigations`, `get_mitigation`, `search_mitigations`, `get_service_health`, `get_cache_stats`. 3 resources `finos://{frameworks,risks,mitigations}/{id}`. Fetches **live from GitHub at runtime** (Contents API, 1h cache, "live discovery only"). IDs are filename-derived (`10_prompt-injection`), **not** `AIR-SEC-010`. No mapping resolution, no graph queries, no derived IDs. No tags or releases. | [repo](https://github.com/finos/aigf-mcp-server), [blog](https://www.finos.org/blog/operationalizing-ai-governance-finos-aigf-mcp-server) |

**Differentiation for our AIGF server:** offline vendored content with pinned provenance; the public `AIR-*` IDs agents actually see in the published framework; resolved crosswalks (control → NIST control title + URL); bidirectional risk/control graph; typed structured output on every tool; citation-ready resources; measured retrieval quality.

### 1.2 CDM (finos/common-domain-model)

| Fact | Detail | Source |
|---|---|---|
| JSON Schema distribution | Maven Central `org.finos.cdm:cdm-json-schema` zip. `7.2.0` = 944,682 bytes (2026-08-25); `6.27.0` = 392,238 bytes. No GitHub release assets. | [maven-metadata](https://repo1.maven.org/maven2/org/finos/cdm/cdm-json-schema/maven-metadata.xml) |
| Hosted per-file schemas | `https://cdm.finos.org/schemas/{7.0|6.0|5.20.0|5.13.0}/{name}.schema.json`. 7.0 page reports 1136 schemas; 6.0 reports 845. | [index](https://cdm.finos.org/schemas/) |
| Schema shape | One file per type/enum/meta wrapper, `cdm-<namespace-dashed>-<Type>.schema.json`. `$ref` are **bare sibling filenames**. `$schema` is **draft-04**. No `$id`; a non-standard `$anchor` holds the namespace. `required` and `minItems`/`maxItems` are emitted. | verified files |
| **Format mismatch** | The JSON Schema models the **legacy CDM ≤6 JSON** (`{"value":..,"meta":{..}}`, choice types as one-property objects). CDM 7 uses **Rune JSON** (`@type`, `@key`, `@ref`, `@scheme`, `@model`, `@version`). 7.x sample files are Rune-format and will **not** validate against the published schema. | [serialization docs](https://cdm.finos.org/docs/serialization/), [CDM 7 blog](https://www.finos.org/blog/cdm-7-a-major-evolution-of-the-common-domain-model) |
| Python distribution | PyPI **`finos-cdm`** (not `python-cdm`), latest `7.2.0`, Python ≥3.11, `pydantic>=2.10.3`, `rune.runtime>=2.2.0`. `BaseDataClass.rune_deserialize(..., validate_model=True, check_rune_constraints=True)` validates cardinality **and Rune `condition`s**. Import style `from finos.cdm.event.common.TradeState import TradeState`. Only 7.x published. | [PyPI](https://pypi.org/project/finos-cdm/), [rune-python-runtime](https://github.com/regnosys/rune-python-runtime) |
| Samples (master/7.x) | `rosetta-source/src/main/resources/functions/` (164 JSON, `*-func-input.json` / `*-func-output.json`, BusinessEvent roots with `eventQualifier`), `.../ingest/output/` (799 FpML-derived TradeState/WorkflowStep JSON). 6.27.0 tag keeps the legacy `cdm-sample-files/` (354 JSON). | git tree |
| Root types | 16 `[rootType]`s incl. `TradeState`, `BusinessEvent`, `WorkflowStep`, `Instruction`, `LegalAgreement`, `CollateralPortfolio`. **No bare `Product` type in 7.x**; products are `NonTransferableProduct`, `TransferableProduct`, `TradableProduct`, with `EconomicTerms.payout` a `choice`. | `.rosetta` source |
| Event qualification | Exactly 35 `func Qualify_*` `[qualification BusinessEvent]` (Execution, Termination, PartialTermination, ContractFormation, Novation, Allocation, Exercise, Reset, ClearedTrade, Compression, Increase, IndexTransition, StockSplit, CreditEventDetermined, ...). | [event-qualification-func.rosetta](https://github.com/finos/common-domain-model/blob/master/rosetta-source/src/main/rosetta/event-qualification-func.rosetta) |
| License | Community Specification License 1.0. Attribution (name, version, source) required when redistributing the materials. | `LICENSE.md` |
| Existing MCP server | None found. | GitHub/npm search |

**Design consequence:** `validate_object` must be a **dual validator**. Auto-detect format (`@type`/`@model` keys → Rune) and route to `finos-cdm` Pydantic for Rune JSON, JSON Schema (draft-04 via `jsonschema.Draft4Validator` with a filename-based `referencing` registry) for legacy JSON. Report which path ran. This is the single most valuable and most subtle piece of the project; it is what makes the tool trustworthy.

### 1.3 FDC3 (finos/FDC3)

| Fact | Detail | Source |
|---|---|---|
| Layout | Monorepo. Context schemas at `packages/fdc3-context/schemas/context/*.schema.json` (34 on `main`; 29 in the 2.2.3 tarball). API/wire schemas at `packages/fdc3-schema/schemas/api/`. | [tree](https://github.com/finos/FDC3/tree/main/packages/fdc3-context/schemas/context) |
| Intent names | `packages/fdc3-standard/src/intents/Intents.ts` (`StandardIntent` union, 19 names incl. deprecated `ViewContact`; `GetUser` only in `next`). Also `standard intents.json` (space in filename). | [Intents.ts](https://raw.githubusercontent.com/finos/FDC3/main/packages/fdc3-standard/src/intents/Intents.ts) |
| **Intent ↔ context mapping** | **Not machine-readable anywhere.** Lives only in `## Possible Contexts` bullet lists in `website/docs/intents/ref/*.md` (20 files), plus optional result-type prose. | [intents/ref](https://github.com/finos/FDC3/tree/main/website/docs/intents/ref) |
| Context types | 2.2 spec: 22 standard + 5 `@experimental` (`order`, `orderList`, `product`, `trade`, `tradeList`) + `fileAttachment` = 28 `type` consts. `next` adds 5 `fdc3.security.*`. | [context spec](https://fdc3.finos.org/docs/context/spec) |
| Schema mechanics | draft-07. Every type is `allOf: [{properties}, {"$ref": "context.schema.json#/definitions/BaseContext"}]` (relative sibling ref). `context.schema.json` uses `unevaluatedProperties` (a 2019-09 keyword inside a draft-07 doc). `$id` in repo and tarball is always `https://fdc3.finos.org/schemas/next/context/<name>.schema.json`; website serves versioned copies at `/schemas/2.2/...`. Gotcha: `security.user.schema.json` has `$id` ending `user.schema.json`. | verified files |
| Versions | Latest release `v2.2.3` (2026-05-14). `v3.0.0-alpha.2` (2026-06-22) is prerelease; the "3.0 adds MCP integration" claim in an LF newsletter is **unverified** (nothing in repo/docs/blog). | [releases](https://github.com/finos/FDC3/releases) |
| npm | `@finos/fdc3-context@2.2.3` ships `dist/schemas/context/*.schema.json` (252 kB). | `npm pack --dry-run` |
| License | Spec: Community Specification License 1.0. Code/npm: Apache-2.0. | `LICENSE.md` |
| Existing MCP server | `novavi/mcp-fdc3` (TS, 1 star, "very early experiment") does the opposite thing: returns FDC3 actions as MCP resources. No catalogue/validation server exists. | [repo](https://github.com/novavi/mcp-fdc3) |

**Design consequence:** ship a generator that parses the 20 intent markdown files into `intents.json` (name, possible contexts, result type, deprecated flag, version-added) and a drift test that fails CI if regeneration changes the checked-in table. Validate contexts with `jsonschema` Draft 2019-09 (superset of draft-07 that understands `unevaluatedProperties`), with a registry keyed by both `$id` and filename.

### 1.4 Toolchain facts (verified 2026-09-04)

| Package | Version | Notes |
|---|---|---|
| `mcp` (official Python SDK) | **2.1.1** | 2.x renamed `FastMCP` → `MCPServer` (`from mcp.server import MCPServer`). Transport args moved to `run()`. Context is injected as a typed `ctx: Context` parameter. Errors: `ToolError` (model sees message, `is_error=True`) vs `MCPError` (JSON-RPC error). Middleware: `async (ctx: ServerRequestContext, call_next) -> HandlerResult`, registered via `MCPServer(name, middleware=[...])`; raise `MCPError` to reject. In-memory testing: `async with Client(server, raise_exceptions=True) as c`. Structured output derives `output_schema` from the return annotation; Pydantic models are unwrapped, primitives wrapped as `{"result": ...}`. Tool annotations via `ToolAnnotations(read_only_hint=True, open_world_hint=False)`. Supports the 2026-07-28 MCP spec. Python ≥3.10. [migration guide](https://py.sdk.modelcontextprotocol.io/migration/) |
| `pydantic` | 2.13.5 | |
| `jsonschema` + `referencing` | 4.26.0 / 0.37.0 | Draft-04 for CDM, Draft 2019-09 for FDC3. |
| `finos-cdm` + `rune.runtime` | 7.2.0 / 2.2.0 | Python ≥3.11. Pulls the entire CDM as Pydantic. Optional extra. |
| `anthropic` | 1.3.0 | 1.x (httpx2). `client.beta.messages.tool_runner`, `anthropic.lib.tools.mcp.async_mcp_tool` (written against `mcp` 1.x `ClientSession`; compatibility with `mcp` 2.x must be checked in week 4, see §11). `client.messages.parse(output_format=Model)` for the grader. |
| `deepeval` | 4.2.1 | `AnthropicModel(model=..., temperature=0)` as judge; `LLMTestCase(input, actual_output, expected_output, retrieval_context, tools_called, expected_tools)`; `GEval`, `ToolCorrectnessMetric`, `ContextualRecallMetric`; runs under `deepeval test run` (pytest plugin). Set `DEEPEVAL_TELEMETRY_OPT_OUT=YES` in CI. |
| `bm25s` / `rapidfuzz` | 0.3.11 / 3.14.6 | Lexical search, no model download. |
| `langgraph` / `langchain-mcp-adapters` | 1.2.11 / 0.3.2 | For the ship example. |
| `uv` | 0.11.21 (installed) | Workspace + lockfile + `uv python install 3.12`. |

Local machine has Python 3.11 on PATH; `uv python install 3.12` handles the target interpreter without touching the system install.

---

## 2. Architecture

```
finos-mcp/
├── pyproject.toml                 # uv workspace root; ruff/mypy/pytest config; no code
├── uv.lock
├── README.md                      # the "nothing writes to external systems" statement lives here, above the fold
├── LICENSE                        # Apache-2.0 (our code)
├── NOTICE                         # attribution for AIGF (CC-BY-4.0), CDM + FDC3 (Community Spec License 1.0)
├── SECURITY.md · CONTRIBUTING.md · CODE_OF_CONDUCT.md · CHANGELOG.md
├── .github/workflows/             # ci.yml, llm-evals.yml, vendor-check.yml, release.yml
├── .pre-commit-config.yaml
│
├── core/                          # package: finos-mcp-core   (import: finos_mcp.core)
│   └── src/finos_mcp/core/
│       ├── server.py              # build_server(): MCPServer factory that installs the safety stack
│       ├── policy.py              # SafetyPolicy: read-only enforcement, size caps, per-tool rate limits
│       ├── ratelimit.py           # token-bucket limiter keyed by (session, tool)
│       ├── audit.py               # JSONL audit log (stderr or file), never stdout
│       ├── errors.py              # ErrorEnvelope + helpers that raise ToolError with a JSON body
│       ├── catalog.py             # generic Document/Catalog + BM25 + fuzzy-id resolution
│       ├── schema.py              # JSON Schema registry helpers (draft-04/2019-09, filename $refs)
│       ├── vendor.py              # SOURCE.json provenance model + verify()
│       ├── metrics.py             # in-process counters/latency histogram; server_info tool
│       └── models.py              # shared Pydantic bases (Citation, Page, SearchHit, ToolMeta)
│
├── servers/
│   ├── aigf/                      # package: finos-mcp-aigf   (import: finos_mcp.aigf)
│   │   ├── src/finos_mcp/aigf/{server.py,models.py,parser.py,tools.py,resources.py,prompts.py,__main__.py}
│   │   ├── src/finos_mcp/aigf/_vendor/   # docs/_risks, docs/_mitigations, docs/_data/references, SOURCE.json
│   │   ├── scripts/sync_upstream.py
│   │   └── tests/
│   ├── cdm/                       # package: finos-mcp-cdm    (import: finos_mcp.cdm)
│   │   ├── src/finos_mcp/cdm/{server.py,models.py,registry.py,validate.py,events.py,tools.py,__main__.py}
│   │   ├── src/finos_mcp/cdm/_vendor/    # schemas/7.x/*.schema.json (zip contents), samples/, qualify.json, SOURCE.json
│   │   ├── scripts/{sync_upstream.py,extract_qualify.py}
│   │   └── tests/
│   └── fdc3/                      # package: finos-mcp-fdc3   (import: finos_mcp.fdc3)
│       ├── src/finos_mcp/fdc3/{server.py,models.py,registry.py,intents.py,tools.py,__main__.py}
│       ├── src/finos_mcp/fdc3/_vendor/   # schemas/context/*.schema.json, intents.json, SOURCE.json
│       ├── scripts/{sync_upstream.py,generate_intents.py}
│       └── tests/
│
├── evals/                         # package: finos-mcp-evals (not published)
│   ├── golden/{aigf,cdm,fdc3}/    # input + expected structured output pairs
│   ├── retrieval/aigf_questions.jsonl      # 50 questions, expected IDs, difficulty tags
│   ├── agent/                     # agent-in-the-loop tests (Claude + in-memory MCP)
│   ├── perf/                      # latency benchmark
│   ├── metrics/collect.py         # writes metrics.json + GitHub job summary
│   └── conftest.py
│
├── examples/
│   ├── claude_desktop_config.json
│   ├── langgraph_agent.py
│   ├── inspector.md               # `npx @modelcontextprotocol/inspector` walkthrough
│   └── demo.tape                  # VHS script that produces demo.gif reproducibly
└── docs/
    ├── tools.md                   # generated tool reference (from output_schema)
    ├── safety.md                  # threat model + what the core enforces
    └── metrics.md                 # what is measured and where to find the numbers
```

Key architectural rules:

1. **Three processes, one core.** Each server is an independent console script (`finos-mcp-aigf`, `finos-mcp-cdm`, `finos-mcp-fdc3`) so a host can enable one without loading `finos-cdm`'s heavy Pydantic tree. A fourth optional entry point `finos-mcp` mounts all three under a single process for HTTP deployments.
2. **Vendored, pinned, offline.** No network at runtime. Every `_vendor/` directory carries `SOURCE.json` (`upstream_repo`, `ref`, `commit_sha`, `fetched_at`, `license`, per-file `sha256`). `vendor.verify()` runs at server start and in tests; a mismatch fails fast.
3. **Typed in, typed out.** Every tool takes Pydantic input (one model per tool, `extra="forbid"`) and returns a Pydantic model, so MCP 2.x publishes `output_schema` automatically and hosts get `structured_content`.
4. **Read-only is enforced, not asserted.** `build_server()` refuses to register a tool whose `ToolAnnotations.read_only_hint` is not `True`. There is no override flag. A test in `core` asserts this for all three servers.
5. **Stdout is sacred.** Under stdio transport stdout is the protocol channel. Audit and logs go to stderr or a file. `core` installs a guard that redirects stray `print()` to stderr.

---

## 3. Core package (`finos-mcp-core`)

### 3.1 Server factory

```python
# finos_mcp/core/server.py
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False,
                            idempotent_hint=True, open_world_hint=False)

def build_server(name: str, *, version: str, instructions: str,
                 policy: SafetyPolicy) -> MCPServer:
    audit = AuditLog.from_env()
    limiter = RateLimiter(policy)
    server = MCPServer(name, version=version, instructions=instructions,
                       middleware=[size_guard(policy), limiter.middleware,
                                   audit.middleware, metrics.middleware])
    server._finos_policy = policy       # read by register_tool
    return server

def register_tool(server, fn, *, name, description, limit: RateLimit | None = None):
    # enforce rule 4: read-only or refuse to start
    server.tool(name=name, description=description, annotations=READ_ONLY)(fn)
    server._finos_policy.register(name, limit)
```

Middleware order matters: size guard first (cheapest rejection), then rate limiter, then audit (so rejected calls are still audited via the `finally`), then metrics.

### 3.2 SafetyPolicy

```python
class RateLimit(BaseModel):
    calls: int = 60          # per window
    window_s: float = 60.0
    burst: int = 10

class SafetyPolicy(BaseModel):
    max_input_bytes: int = 64 * 1024          # per tool call, serialized arguments
    max_output_bytes: int = 512 * 1024        # truncate + flag, never silently
    default_limit: RateLimit = RateLimit()
    per_tool: dict[str, RateLimit] = {}       # e.g. validate_object gets calls=30
    max_search_results: int = 50
    audit_hash_inputs: bool = True            # log sha256(args), not raw args
```

Policy is loaded from defaults, then `FINOS_MCP_*` env vars, then an optional `finos-mcp.toml`. Only tightening is possible from the environment (a lower limit wins); the read-only rule is not configurable.

### 3.3 Rate limiter

Token bucket per `(session_id, tool_name)`. Session id comes from the MCP session in `ServerRequestContext`; for stdio there is exactly one session. On exhaustion the middleware raises `MCPError(code=-32029, message="rate_limited", data={"tool": name, "retry_after_s": x})` so the host sees a clean JSON-RPC error and the model is not fed a misleading tool result. Buckets are pruned on an LRU basis (max 10k keys) so an HTTP deployment cannot be memory-exhausted through session churn.

### 3.4 Structured errors

Every failure the model *could* fix is raised as `ToolError` whose message is a JSON `ErrorEnvelope`:

```python
class ErrorEnvelope(BaseModel):
    code: Literal["not_found", "ambiguous_id", "invalid_input", "input_too_large",
                  "validation_failed", "unsupported_format", "internal"]
    message: str
    hint: str | None = None              # e.g. "Did you mean AIR-SEC-010?"
    candidates: list[str] = []           # for ambiguous_id
    retryable: bool = False
    details: dict[str, Any] = {}
```

`ambiguous_id` with `candidates` is what turns "get_control('prompt injection')" from a dead end into a one-step recovery for the agent. Unexpected exceptions are left to the SDK, which logs the traceback and gives the model only `"Error executing tool <name>"`, which is exactly the no-leak behaviour we want.

### 3.5 Audit log

JSON lines, one per call, to `FINOS_MCP_AUDIT_PATH` (default stderr):

```json
{"ts":"2026-09-04T12:00:00Z","server":"finos-mcp-aigf","session":"…","request_id":"…",
 "method":"tools/call","tool":"get_control","args_sha256":"…","args_bytes":41,
 "outcome":"ok","duration_ms":3.2,"result_bytes":1820}
```

Outcomes: `ok`, `tool_error:<code>`, `rate_limited`, `input_too_large`, `internal`. Arguments are hashed by default so the log never becomes a second copy of the agent's inputs; `FINOS_MCP_AUDIT_RAW_ARGS=1` opts in for debugging.

### 3.6 Catalog and search

A generic `Catalog[T]` holds documents with `id`, `aliases`, `title`, `body`, `sections`. `resolve(id_or_text)` normalises across every ID form a model might emit (`AIR-SEC-010`, `air-sec-10`, `ri-10`, `10`, `prompt injection`) and returns exactly one record or raises `ambiguous_id` with candidates. Search is BM25 over section-level chunks (`bm25s`) plus a rapidfuzz title boost, returning `SearchHit(id, title, section, score, snippet, citation_uri)`. No embeddings by default: it keeps startup under 200 ms and removes a model download. An optional `[embeddings]` extra can be evaluated later if recall@5 on the eval set is below target (see §7).

### 3.7 Schema registry helper

`SchemaRegistry.from_directory(path, dialect=Draft4|Draft201909, key_by=("filename", "$id"))` builds a `referencing.Registry` with a retriever that resolves bare sibling filenames (CDM) and absolute `$id`s plus filename fallbacks (FDC3). It also caches compiled validators and exposes `validate(instance, root_schema) -> list[ValidationIssue]` where each issue carries `json_path`, `schema_path`, `message`, `validator`, so `validate_object` can return precise, machine-usable results instead of one exception string.

### 3.8 Metrics

An in-process `Metrics` object records per-tool call count, error count, and a latency reservoir (p50/p95/p99). Every server exposes one meta tool, `server_info`, returning `ServerInfo(name, version, standard_version, upstream_commit, counts={...}, latency_ms={...})`. The same object is what `evals/perf` reads to log p95 in CI.

---

## 4. AIGF server (`finos-mcp-aigf`) — milestone 1

### 4.1 Vendoring

`scripts/sync_upstream.py --ref <tag|sha>` downloads `docs/_risks/*.md`, `docs/_mitigations/*.md`, `docs/_data/references/*.yml`, and `docs/_config.yml` (for the type labels) from `finos/ai-governance-framework` via the raw URL, writes `SOURCE.json`, and copies `LICENSE` into `_vendor/`. Default ref: **pinned commit SHA on `main`** rather than the `v2` tag, because `main` carries the `owasp-asi`, `atr`, UK and Canada mappings that v2 lacks; the SHA is recorded so the claim "content as of commit X" is verifiable. The weekly `vendor-check.yml` workflow re-runs sync in a scratch dir and opens a PR if anything changed.

### 4.2 Parser and models

```python
class ExternalRef(BaseModel):
    framework: str            # "nist-sp-800-53r5"
    key: str                  # "sa-9"
    title: str | None         # resolved from docs/_data/references/<framework>.yml
    url: str | None
    issuer: str | None

class Risk(BaseModel):
    id: str                   # "AIR-SEC-010"
    short_id: str             # "ri-10"
    sequence: int
    type: Literal["RC","OP","SEC"]
    type_label: str           # "Security"
    title: str
    status: Literal["Pre-Draft","Draft","Working-Group-Approved","Approved-Specification"]
    summary: str              # first section body
    sections: list[Section]   # heading + markdown body, in order
    related_risks: list[str]  # AIR-* ids
    mitigated_by: list[str]   # AIR-PREV-*/AIR-DET-* ids (computed by inverting `mitigates`)
    references: list[ExternalRef]
    source_path: str          # docs/_risks/ri-10_prompt-injection.md
    citation_uri: str         # aigf://risk/AIR-SEC-010

class Control(BaseModel):     # AIGF calls these "mitigations"; we expose both words
    id: str                   # "AIR-PREV-020"
    short_id: str             # "mi-20"
    type: Literal["PREV","DET"]
    ... same shape ...
    mitigates: list[str]
    related_controls: list[str]
```

Parsing uses `python-frontmatter` (handles `---` blocks) with `yaml.safe_load`, which tolerates inline comments. Body is split on `##` headings into `Section`s. A parser test asserts 23 risks, 23 controls, that every `mitigates`/`related_*` reference resolves, that every `*_references` key has a dataset file, and that every key in those lists exists in the dataset (this replicates upstream's `validate-references.py` and will catch upstream drift on sync).

### 4.3 Tools

| Tool | Input | Output | Rate limit |
|---|---|---|---|
| `list_risks` | `type?: RC\|OP\|SEC`, `status?`, `page?`, `page_size? (≤50)` | `Page[RiskSummary]` (id, title, type, status, mitigated_by count) | default |
| `get_risk` | `id: str` (any form) | `Risk` | default |
| `list_controls` | `type?: PREV\|DET`, `page?` | `Page[ControlSummary]` | default |
| `get_control` | `id: str`, `include_sections?: bool = true` | `Control` | default |
| `map_risks_to_controls` | `risk_ids: list[str] (≤25)` \| `query: str` | `Mapping(risks=[…], controls=[…], edges=[(risk_id, control_id)], uncovered_risks=[…])` | default |
| `map_control_to_external` | `id`, `frameworks?: list[str]` | `Crosswalk(control_id, refs=[ExternalRef])` | default |
| `search_framework` | `query`, `scope?: risks\|controls\|all`, `k? (≤20)` | `list[SearchHit]` with `citation_uri` per hit | 120/min |
| `list_reference_frameworks` | – | `list[ReferenceFramework(name, entry_count, issuer)]` | default |
| `server_info` | – | `ServerInfo` | default |

The brief's four tools are all present; `get_risk`, `list_controls`, `map_control_to_external` and `list_reference_frameworks` are added because an agent doing a governance review needs the reverse direction and the regulator crosswalk, and because they cost almost nothing on top of the parsed catalog.

### 4.4 Resources (citation surface)

- `aigf://risk/{id}` and `aigf://control/{id}` → the **raw vendored markdown**, `text/markdown`, with a header block giving `id`, `title`, `upstream commit`, `source path`, and the canonical URL `https://air-governance-framework.finos.org/…`. This is what an agent should quote.
- `aigf://risk/{id}/section/{slug}` → one section, for tight citations.
- `aigf://reference/{framework}` → the reference dataset as JSON.
- `aigf://index` → machine-readable catalog (all ids, titles, edges) so a host can prefetch.

### 4.5 Prompts

Two MCP prompts, cheap to add and useful in Claude Desktop: `assess_use_case(description)` ("list applicable AIR risks, then the controls that mitigate each, cite IDs") and `control_gap_analysis(controls_in_place: list[str])`.

### 4.6 Definition of done

- `uv run finos-mcp-aigf` starts in <300 ms, offline, and passes `npx @modelcontextprotocol/inspector` smoke.
- Claude Desktop answers "What controls mitigate prompt injection?" with `AIR-PREV-*` IDs and a resource citation.
- ≥40 unit tests, ≥90% coverage on `finos_mcp.aigf`.
- `evals/golden/aigf` has 15 cases; `metrics.json` reports `aigf.risks=23`, `aigf.controls=23`, `aigf.reference_frameworks=14`, `aigf.crosswalk_entries=N`.

---

## 5. CDM server (`finos-mcp-cdm`) — milestone 2

### 5.1 Vendoring

`sync_upstream.py --version 7.2.0` downloads `cdm-json-schema-7.2.0.zip` from Maven Central, verifies its size and sha256 against `SOURCE.json`, unzips into `_vendor/schemas/`. It also pulls a curated sample set (about 40 files) from `rosetta-source/src/main/resources/functions/business-event/**/…-func-output.json` and `ingest/output/fpml-confirmation-to-trade-state/fpml-5-13-products-interest-rate-derivatives/*.json` at the matching tag, plus a handful of **legacy-format** samples from the `6.27.0` tag so the JSON Schema path has real positive cases. `extract_qualify.py` parses `event-qualification-func.rosetta` with a small regex-based extractor into `qualify.json` (function name, docstring, the `[qualification BusinessEvent]` conditions as text, referenced instruction types). It is checked in and covered by a drift test.

Vendored size: ~1 MB of schema JSON plus ~2 MB of samples; acceptable for a wheel. Samples are marked `package-data`, schemas too.

### 5.2 Dual validation strategy

```
validate_object(object, type?, format="auto")
   │
   ├─ detect: any of {"@type","@model","@version","@key","@ref"} at any depth → "rune"
   │          else → "legacy"
   │
   ├─ rune   → finos-cdm Pydantic: resolve class from `@type` or `type` param,
   │           model.rune_deserialize(json, validate_model=True, check_rune_constraints=True,
   │           strict=True, raise_validation_errors=False) → collect errors
   │           (cardinality, enums, AND Rune `condition`s that JSON Schema cannot express)
   │
   └─ legacy → jsonschema Draft4Validator against cdm-<ns>-<Type>.schema.json
               with the filename-resolving registry → iter_errors → ValidationIssue list
```

Output:

```python
class ValidationReport(BaseModel):
    valid: bool
    format_detected: Literal["rune","legacy"]
    validator: Literal["finos-cdm 7.2.0 (pydantic)","json-schema draft-04 (cdm-json-schema 7.2.0)"]
    type: str                          # "cdm.event.common.TradeState"
    issues: list[ValidationIssue]      # json_path, message, kind (cardinality|type|enum|condition|unknown_field)
    warnings: list[str]                # e.g. "legacy schema does not enforce Rune conditions"
    stats: dict[str,int]               # nodes visited, refs resolved
```

`finos-cdm` is an optional extra (`finos-mcp-cdm[rune]`) because it is large. Without it, Rune-format input returns `unsupported_format` with a hint naming the extra; with it, both paths work. CI installs the extra. This honesty is deliberate: the tool never claims a document is valid when it only checked shape.

Input cap for this tool is raised to 1 MiB (FpML-derived TradeStates are big) and its rate limit lowered to 30/min because Pydantic validation of a large TradeState can take tens of milliseconds.

### 5.3 Type registry

`registry.py` loads all schema files once (lazy per namespace, then cached), builds an index `TypeName → (namespace, file, kind ∈ {type, enum, choice, metaWrapper})`, extracts `description`, `properties` with per-field `type`, `cardinality` (from `required`/`minItems`/`maxItems`), `enum values` with titles, and sibling `$ref` targets. Root types are read from a checked-in list of the 16 `[rootType]`s (verified against `.rosetta` source in the drift test).

### 5.4 Tools

| Tool | Input | Output |
|---|---|---|
| `describe_type` | `name` (`TradeState` or `cdm.event.common.TradeState`), `depth? (0-2)`, `include_enums?` | `TypeDescription(name, namespace, kind, description, fields=[Field(name, type, cardinality, description, is_ref, enum_values?)], root_type: bool, used_by: list[str] (top 20 referrers), schema_uri)` |
| `list_types` | `namespace?` (`cdm.product.*`), `kind?`, `root_only?`, `page` | `Page[TypeSummary]` |
| `list_products` | – | Curated view: the product template types (`NonTransferableProduct`, `TransferableProduct`, `TradableProduct`, `EconomicTerms`) and every `Payout` alternative (`InterestRatePayout`, `CreditDefaultPayout`, `OptionPayout`, `EquityPayout`…) with one-line descriptions and sample availability. Exists because the brief asked for it and "which payout types exist" is the real question; documented as a view over `describe_type`. |
| `validate_object` | `object: dict`, `type?`, `format?: auto\|rune\|legacy` | `ValidationReport` |
| `explain_event` | `event: dict` \| `qualifier: str` | `EventExplanation(qualifier, qualify_function, conditions_text, instruction_types, before_states, after_states, product_summaries, sample_uri?)`. Given a BusinessEvent JSON: read `eventQualifier`, count `instruction[].primitiveInstruction` kinds, summarise `after[].trade.product` (payout types, parties, notional/currency where present). Given a name: describe the `Qualify_*` function and point to a vendored sample. |
| `search_types` | `query`, `k` | `list[SearchHit]` over type names + descriptions |
| `get_sample` | `name` | `Sample(name, format, root_type, json)` |
| `server_info` | – | counts: schemas, types, enums, root types, qualify functions, samples |

### 5.5 Resources

`cdm://schema/{TypeName}` (raw JSON Schema file), `cdm://sample/{name}`, `cdm://qualify/{Qualify_Name}` (the Rune function text), `cdm://index`.

### 5.6 Definition of done

- Every vendored Rune sample validates `valid=true` via the Pydantic path; every vendored legacy sample validates via the schema path; ≥10 hand-mutated negatives (missing `tradeDate`, wrong enum, cardinality 2 where max 1, unknown field, malformed `@ref`) produce the expected `issue.kind` and `json_path`.
- `describe_type("TradeState")` round-trips to the exact `required` list in the schema.
- `metrics.json`: `cdm.schemas≈1136`, `cdm.root_types=16`, `cdm.qualify_functions=35`, `cdm.samples=N`.
- p95 for `validate_object` on the median sample < 50 ms; `describe_type` < 5 ms.

---

## 6. FDC3 server (`finos-mcp-fdc3`) — milestone 3

### 6.1 Vendoring

`sync_upstream.py --ref v2.2.3` fetches `packages/fdc3-context/schemas/context/*.schema.json` and `website/docs/intents/ref/*.md` and `packages/fdc3-standard/src/intents/Intents.ts`. Default pin is the **released** `v2.2.3`, with `--ref main` supported to preview 3.0 (`fdc3.security.*`, `GetUser`). `SOURCE.json` records both the git ref and the `$id` base the schemas use.

`generate_intents.py` parses the markdown: title from frontmatter, `## Possible Contexts` bullets (link text → `fdc3.*` type via the context schema `type` const), `## Result Type` / "SHOULD return" prose → result type, `deprecated` from a `:::caution` block or "deprecated" wording, and cross-checks every name against `Intents.ts`. Output `intents.json`:

```json
{"name":"ViewChart","contexts":["fdc3.chart","fdc3.instrument","fdc3.instrumentList","fdc3.portfolio","fdc3.position"],
 "result":null,"deprecated":false,"since":"1.0","doc_path":"website/docs/intents/ref/ViewChart.md"}
```

A drift test regenerates and diffs. Because upstream prose can change shape, the generator is defensive and the checked-in JSON is the runtime source of truth; a human reviews the diff in the weekly vendor PR.

### 6.2 Schema registry

Draft 2019-09 validator (superset of draft-07 that implements `unevaluatedProperties`). Registry keyed by `$id` (`…/schemas/next/context/<name>.schema.json`), by the versioned form (`…/schemas/2.2/…`), and by bare filename, so any `$ref` style resolves. Special-case the `security.user` filename/`$id` mismatch. Index `type` const → schema for every file (28 on 2.2.3, 33 on main).

### 6.3 Tools

| Tool | Input | Output |
|---|---|---|
| `list_intents` | `include_deprecated?`, `context_type?` (filter) | `list[IntentSummary(name, contexts, result, deprecated)]` |
| `get_intent` | `name` | `Intent(... + doc excerpt + citation_uri)` |
| `list_context_types` | `experimental?: bool` | `list[ContextTypeSummary(type, title, schema_uri, experimental, used_by_intents)]` |
| `get_context_schema` | `type` (`fdc3.instrument`) \| `name` (`instrument`), `resolve_refs?: bool` | `ContextSchema(type, schema (dereferenced optional), required, properties summary, example)` |
| `validate_context` | `context: dict`, `type?` | `ValidationReport` (same core model as CDM; `format_detected` omitted) with `issues[].json_path` |
| `suggest_intent` | `context: dict` \| `context_type: str`, `goal?: str` | `list[IntentSuggestion(name, score, reason, result)]`: exact type match first, then structural match (validate the object against every schema and rank by fewest issues, useful when `type` is missing or wrong), then optional BM25 on `goal` against intent descriptions. |
| `find_intents_by_context` | `context_type` | thin alias mirroring the FDC3 API name so agents that know FDC3 find it |
| `server_info` | – | counts: intents, context types, schemas, fdc3 version |

### 6.4 Resources

`fdc3://schema/{type}` (raw schema, `application/schema+json`), `fdc3://intent/{name}` (raw markdown doc), `fdc3://intents` (the generated table), `fdc3://index`.

### 6.5 Definition of done

- All 20 intents parsed with non-empty contexts (except any legitimately empty upstream) and every context name resolves to a schema `type`.
- Each context schema's own `example` (where present) validates; a negative set (wrong `type`, missing `id.ticker` shape, extra property where `unevaluatedProperties:false`) fails with the right path.
- `suggest_intent({"type":"fdc3.instrument","id":{"ticker":"AAPL"}})` returns `ViewInstrument`, `ViewChart`, `ViewQuote`, `ViewNews`, `ViewAnalysis`, `ViewHoldings`, `ViewInteractions`, `ViewOrders`, `ViewResearch` (9) with `ViewInstrument` first.
- `metrics.json`: `fdc3.intents=19`, `fdc3.context_types=28`, `fdc3.schemas=29`.

---

## 7. Evals (`evals/`) — milestone 5 (built incrementally from week 1)

### 7.1 Three tiers, three triggers

| Tier | What | Needs network / key | Trigger |
|---|---|---|---|
| A. Golden + contract | Deterministic pytest over the in-memory `Client`: every tool's `output_schema` snapshot (inline-snapshot), golden input→output pairs, negative cases, read-only enforcement, rate limit and size-cap behaviour, audit line shape. | No | every push / PR |
| B. Retrieval | 50 questions over AIGF → expected `AIR-*` IDs → recall@1/3/5, MRR. Pure Python, deterministic. | No | every push / PR |
| C. Agent-in-the-loop | Claude drives the real servers through MCP; must cite a control ID; DeepEval metrics + LLM judge. | Yes (`ANTHROPIC_API_KEY`) | nightly, `workflow_dispatch`, and PRs labelled `run-llm-evals` |

Tiers A and B are the CI gate. Tier C is reported, not gating, until it has been stable for two weeks; then recall on the cited-ID check becomes a gate too.

### 7.2 Golden tests

`evals/golden/<server>/<case>.json`: `{ "tool": "...", "args": {...}, "expect": {...partial structured_content...}, "expect_error": "code"? }`. A single parametrised test loads all cases, calls through `Client(server)`, and asserts with a partial-match helper (so adding a field upstream does not break 40 cases). Snapshot tests (`inline_snapshot`) pin each tool's `input_schema`/`output_schema` so an accidental contract change is a visible diff in review.

### 7.3 Retrieval set (50 questions)

`evals/retrieval/aigf_questions.jsonl`, one per line:

```json
{"id":"q07","question":"Which controls address prompt injection in an agent that calls MCP servers?",
 "expected":["AIR-PREV-020","AIR-SEC-010"],"kind":"control_lookup","difficulty":"medium",
 "author":"manual","notes":"needs both the risk and its mitigations"}
```

Composition target: 15 direct lookups (title paraphrases), 15 concept questions (no title words), 10 crosswalk questions ("what maps to NIST SA-9?"), 10 multi-hop ("risks mitigated by detective controls about logging"). Written by hand against the vendored content, with expected IDs reviewed once by reading the source file. Recall@k is computed over `search_framework` results, and separately over a tiny "router" that also calls `map_control_to_external` for crosswalk questions, so we can report search-only vs tool-assisted retrieval. Targets: recall@5 ≥ 0.85 search-only, ≥ 0.95 tool-assisted; MRR reported. If search-only misses, the first lever is section-level chunking and title boosting, the second is the optional embeddings extra.

DeepEval's `ContextualRecallMetric` is an LLM-judged metric and is not the same as exact recall@k; we compute recall@k ourselves and use DeepEval for tier C.

### 7.4 Agent-in-the-loop (Claude)

Harness in `evals/agent/harness.py`:

- Start each server in-process, connect with the MCP 2.x `Client`, convert `list_tools()` to Anthropic tool definitions. Preferred path is `anthropic.lib.tools.mcp.async_mcp_tool` with `client.beta.messages.tool_runner`; it was written against `mcp` 1.x's `ClientSession`, so week 4 begins with a compatibility spike and a 40-line fallback adapter (tool dict from `input_schema`, execute via `client.call_tool`, feed back `tool_result`) if the helper rejects the 2.x client.
- Model under test: `claude-opus-5` by default (`EVAL_MODEL` env to override), adaptive thinking, `max_tokens=16000`, streaming. Because the model can return `stop_reason: "refusal"` on Opus 5, the harness enables the server-side fallback beta (`fallbacks: "default"`) and checks `stop_reason` before reading content.
- 20 tasks, e.g. "A team wants to deploy a RAG chatbot over internal documents. Name the top three AIGF risks and, for each, one control, citing IDs." Each task carries `must_cite: ["AIR-…"]` (at least one of) and `must_call: ["search_framework" | "map_risks_to_controls"]`.
- Assertions: (1) deterministic: every cited `AIR-*` ID in the answer exists in the catalog (no hallucinated IDs, regex-extracted), at least one `must_cite` ID appears, the expected tool was called; (2) DeepEval: `ToolCorrectnessMetric` on `tools_called` vs `expected_tools`, `GEval` "Cited controls are relevant and the reasoning references their content" with `AnthropicModel(model="claude-opus-5", temperature=0)` as judge, `FaithfulnessMetric` with `retrieval_context` = the resource texts the agent actually read.
- Grader output is parsed with `client.messages.parse(output_format=GradeResult)` so the rubric score is typed, not regexed.
- Cost guard: tasks run with `max_tokens` caps and the run aborts if cumulative `usage` exceeds a configured token budget; a run is ~20 × (3–6 turns), well under a dollar on Opus 5.

Equivalent but smaller sets (8 tasks each) exist for CDM ("validate this object and explain the first error") and FDC3 ("which intent should I raise for this context?"), scored on `validate_object`/`suggest_intent` being called and the answer agreeing with the tool's structured result.

### 7.5 Latency benchmark

`evals/perf/bench.py` calls each tool 200× through the in-memory client with representative arguments (tool-call overhead included, no transport), reports p50/p95/p99 per tool, and fails if any p95 exceeds its budget (`describe_type` 5 ms, `search_framework` 25 ms, `validate_object` 50 ms on the median sample, everything else 10 ms). Numbers go into `metrics.json`.

### 7.6 Metrics collection

`evals/metrics/collect.py` runs after tests and writes `metrics.json`:

```json
{"generated_at":"…","commit":"…",
 "exposure":{"aigf.risks":23,"aigf.controls":23,"aigf.reference_frameworks":14,"aigf.crosswalk_entries":0,
             "cdm.schemas":0,"cdm.types":0,"cdm.root_types":16,"cdm.qualify_functions":35,"cdm.samples":0,
             "fdc3.intents":19,"fdc3.context_types":28,"fdc3.schemas":29,"tools_total":0,"resources_total":0},
 "tests":{"count":0,"passed":0,"coverage_pct":0.0},
 "retrieval":{"recall_at_1":0,"recall_at_3":0,"recall_at_5":0,"mrr":0,"questions":50},
 "agent":{"tasks":20,"cited_valid_id_rate":0,"tool_correctness":0,"geval_mean":0,"model":"claude-opus-5"},
 "latency_ms_p95":{"aigf.search_framework":0,"cdm.validate_object":0,"fdc3.validate_context":0}}
```

It also appends a markdown table to `$GITHUB_STEP_SUMMARY`, uploads `metrics.json` as a workflow artifact (90-day retention), and on `main` commits it to a `metrics` branch so `https://raw.githubusercontent.com/<you>/finos-mcp/metrics/metrics.json` is a stable URL for README badges (shields.io endpoint badges: "controls exposed", "recall@5", "p95 latency", "tests"). That is the "verifiable later" requirement: every number on the resume resolves to a CI run.

---

## 8. CI/CD

`ci.yml` (push, PR): matrix `{ubuntu, windows}` × Python 3.12 (and 3.13 allowed-failure), `uv sync --all-extras`, `ruff check`, `ruff format --check`, `mypy --strict`, `pytest -q --cov --cov-report=xml`, vendor `verify()`, drift tests (intents.json, qualify.json), perf bench, `collect.py`, upload artifact, job summary. Concurrency-cancel on same ref. Cache `uv`.

`llm-evals.yml` (nightly cron, manual, label): tier C with `ANTHROPIC_API_KEY` secret and `DEEPEVAL_TELEMETRY_OPT_OUT=YES`; uploads DeepEval's results JSON; comments a summary on the PR.

`vendor-check.yml` (weekly): re-syncs all three upstreams to a temp dir, diffs, opens a PR titled "chore(vendor): AIGF main@<sha>, CDM 7.x.y, FDC3 vX" with the regenerated `intents.json` / `qualify.json` and the parser-test output.

`release.yml` (tag `v*`): build the four wheels, publish to PyPI via trusted publishing (no token secret), build a multi-arch Docker image (`ghcr.io/<you>/finos-mcp`, HTTP transport, non-root, read-only FS) and attach the SBOM (`uv export` + `syft`). CodeQL and Dependabot enabled.

Pre-commit: ruff, ruff-format, mypy on changed packages, `check-added-large-files` with an allowlist for `_vendor/`.

---

## 9. Ship — milestone 6

1. **Claude Desktop config** (`examples/claude_desktop_config.json`) using `uvx` so no install step:
   ```json
   {"mcpServers": {
     "finos-aigf": {"command": "uvx", "args": ["finos-mcp-aigf"]},
     "finos-cdm":  {"command": "uvx", "args": ["--from", "finos-mcp-cdm[rune]", "finos-mcp-cdm"]},
     "finos-fdc3": {"command": "uvx", "args": ["finos-mcp-fdc3"]}}}
   ```
   Plus the equivalent `claude mcp add` commands for Claude Code and a `.mcp.json` for project scope.
2. **LangGraph example** (`examples/langgraph_agent.py`): `MultiServerMCPClient` from `langchain-mcp-adapters` pointing at the three stdio servers, a `create_react_agent` with a system prompt that requires `AIR-*` citations, and a 3-question script. Runs against Claude via `langchain-anthropic`.
3. **MCP Inspector walkthrough** (`examples/inspector.md`) with screenshots of `output_schema` and a `validate_object` failure.
4. **Demo GIF**: `examples/demo.tape` for VHS renders a 2-minute terminal session (start server, inspector call, then a LangGraph run with a cited answer) to `docs/demo.gif`; reproducible, no screen recording needed. A second short GIF from Claude Desktop is optional.
5. **Docs site**: `docs/` served by GitHub Pages (mkdocs-material) with the generated tool reference, safety model, and live metrics badges.
6. **PyPI + GHCR release `v0.1.0`**, GitHub Release notes generated from the CHANGELOG.
7. **Upstream outreach**:
   - PR to `finos/ai-governance-framework` adding the server under a "Community integrations / tooling" section of the README (FINOS requires EasyCLA sign-off on the PR; sign the ICLA first, it is instant for individuals).
   - Issue on `finos/aigf-mcp-server` offering the `AIR-*` ID resolver and offline vendoring as an upstream contribution, linking the eval numbers. This is the most credible way to get noticed by the Citi maintainers.
   - Submit to the MCP registry (`registry.modelcontextprotocol.io`) and the Glama/Smithery indexes where `finos/aigf-mcp-server` is already listed.
   - Post in the FINOS AI Readiness / FDC3 / CDM mailing lists with the demo GIF.

---

## 10. Timeline (5 weeks, ~15 h/week; compressible to 3 weeks full-time)

| Week | Deliverable | Exit criterion |
|---|---|---|
| 1 | Repo scaffold (uv workspace, CI green on empty packages), `core` complete with tests, AIGF sync + parser + all tools + resources, Claude Desktop working end to end | §4.6 met; first `metrics.json` published |
| 2 | CDM sync (schema zip + samples + qualify.json), registry, dual validator, all tools | §5.6 met |
| 3 | FDC3 sync + intents generator + registry + tools; `finos-mcp` combined entry point; docs/tools.md generator | §6.5 met; three servers pass inspector smoke |
| 4 | Retrieval set (50 Qs), recall@k, agent harness (compat spike first), DeepEval metrics, perf bench, `llm-evals.yml` | Tier B ≥ targets; tier C runs green nightly |
| 5 | LangGraph example, demo GIF, docs site, v0.1.0 release, FINOS PR + issue + registry listing; buffer | Everything in §9 live; README metrics badges resolve |

Order within week 1 is deliberately core-then-AIGF: the safety layer is what makes a FINOS reviewer comfortable, and it is easier to build against one real server than in the abstract.

---

## 11. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| `anthropic` MCP helper (`async_mcp_tool`) incompatible with `mcp` 2.x `Client` | Medium | Spike on day 1 of week 4; fallback adapter is 40 lines and already designed (§7.4). |
| `finos-cdm` import time or memory is large (whole CDM as Pydantic) | Medium | Lazy import inside `validate_object`; measure at startup; keep as optional extra; document. |
| CDM JSON Schema zip contents differ from the hosted `/schemas/7.0/` files, or draft-04 quirks (`$anchor`) trip `jsonschema` | Medium | Treat the zip as canonical; sync script asserts file count and spot-checks hashes; pre-strip non-standard `$anchor` at load; test both `Draft4Validator` and `Draft202012Validator` and keep the one that resolves all refs. |
| Upstream FDC3 markdown changes shape and the intents generator silently drops contexts | Medium | Drift test + assertion that no standard intent has zero contexts + weekly vendor PR is human-reviewed. |
| AIGF `main` changes IDs or retires files between syncs | Low | Pin commit SHA; parser test replicates upstream `validate-references`; retrieval set is keyed by ID and the sync PR shows which questions break. |
| `MCPServer` API details (middleware ctx fields, session id) differ from docs | Low | Read the installed package source in week 1; `core` tests exercise middleware through the real in-memory client, not mocks. |
| Licensing: redistributing CDM/FDC3 schemas under Community Spec License 1.0 | Low | `NOTICE` with name, version, source per §1.2 of the license; AIGF CC-BY-4.0 attribution; code Apache-2.0. Vendored dirs carry the upstream LICENSE. |
| DeepEval API churn (4.x) | Low | Pin exact version; keep deterministic assertions independent of DeepEval so tier C still produces the key numbers if a metric class breaks. |
| Tier C cost drift | Low | Token budget abort; nightly only; `EVAL_MODEL` can point at Sonnet 5 for smoke runs. |
| Windows path/encoding issues (dev machine is Windows) | Medium | CI matrix includes Windows; all file IO uses `encoding="utf-8"`; `pathlib` everywhere; audit log newline-normalised. |

---

## 12. Resume-facing metrics (all produced by CI, all resolvable to `metrics.json`)

| Metric | Where it comes from | Expected value |
|---|---|---|
| Controls and risks exposed | `server_info` counts, asserted in tests | 23 risks, 23 controls, 14 reference frameworks, N crosswalk entries |
| CDM schemas / types / root types / qualify functions | registry counts | ~1136 / ~1057 / 16 / 35 |
| FDC3 intents / context types | generated tables | 19 / 28 (2.2.3) |
| Tools and resources | registered counts across three servers | ~24 tools, ~12 resource templates |
| Test count and coverage | pytest + coverage.xml | target ≥250 tests, ≥90% |
| Retrieval recall@5 / MRR | tier B | ≥0.85 search-only, ≥0.95 tool-assisted |
| Agent cited-valid-ID rate | tier C | ≥0.95 over 20 tasks |
| p95 tool latency | perf bench | per-tool budgets in §7.5 |
| Package downloads / stars | PyPI stats, GitHub | reported after launch |

---

## 13. Decisions that deviate from the brief, and why

| Brief said | Plan does | Why |
|---|---|---|
| "official MCP Python SDK" | `mcp` 2.1.1 with `MCPServer` (not the 1.x `FastMCP` class, and not the third-party `fastmcp` package the FINOS server uses) | 2.x is the current stable line and supports the 2026-07-28 spec, structured output, middleware and in-memory testing natively; also a visible difference from the existing FINOS server. |
| "Load the published CDM JSON schema" and validate against it | Dual validator: JSON Schema for legacy JSON, `finos-cdm` Pydantic for Rune JSON, with the path reported | The published schema does not describe CDM 7 documents (§1.2). Schema-only validation would reject every current sample and mislead agents. |
| `list_products` | Kept as a curated view over product template and `Payout` alternatives; `list_types` is the general tool | There is no bare `Product` type in CDM 7. |
| `explain_event` | Grounded in the 35 `Qualify_*` functions and instruction/after-state summaries, not free-form prose | Keeps the tool deterministic and testable; prose belongs to the agent. |
| FDC3 "load the intents schema" | Generate `intents.json` from intent docs + `Intents.ts` with a drift test | No machine-readable intent↔context mapping exists upstream (§1.3). |
| "DeepEval or plain pytest" | Both: deterministic pytest for gates, DeepEval for LLM-judged agent metrics | Gates must not depend on an LLM judge; judged metrics are still worth reporting. |
| "Read-only by default" | Read-only always; no write tools can register | Simpler safety story for FINOS reviewers; there is no legitimate write use case for a standards catalogue. |
| Retrieval set "over AIGF" | AIGF set of 50 plus small CDM/FDC3 agent sets | The 50-question set stays AIGF-only as specified; the other servers get agent tasks so every server has a tier C signal. |
| Demo GIF via screen recording | VHS tape checked in | Reproducible and re-renderable after every change. |

---

## 14. Appendix

### A. Bootstrap commands (week 1, day 1)

```bash
uv python install 3.12
mkdir finos-mcp && cd finos-mcp && git init
uv init --lib core --name finos-mcp-core
uv init --lib servers/aigf --name finos-mcp-aigf
uv init --lib servers/cdm  --name finos-mcp-cdm
uv init --lib servers/fdc3 --name finos-mcp-fdc3
uv init --lib evals        --name finos-mcp-evals
# root pyproject: [tool.uv.workspace] members = ["core","servers/*","evals"]
uv add --package finos-mcp-core "mcp==2.1.1" "pydantic==2.13.5" "jsonschema==4.26.0" "referencing==0.37.0" "bm25s==0.3.11" "rapidfuzz==3.14.6" "python-frontmatter" "pyyaml"
uv add --package finos-mcp-cdm --optional rune "finos-cdm==7.2.0"
uv add --package finos-mcp-evals "anthropic[mcp]==1.3.0" "deepeval==4.2.1" "inline-snapshot" "pytest" "pytest-cov" "anyio"
uv add --dev ruff mypy pytest pytest-cov inline-snapshot
uv sync --all-extras
```

### B. Minimal AIGF server skeleton (MCP 2.x shape)

```python
# servers/aigf/src/finos_mcp/aigf/server.py
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from finos_mcp.core import build_server, register_tool, SafetyPolicy, ErrorEnvelope
from .catalog import load_catalog
from .models import Risk, Control, Mapping, SearchHit, Page

catalog = load_catalog()          # vendored, verified, cached
server = build_server("finos-mcp-aigf", version=__version__,
                      instructions="Read-only access to the FINOS AI Governance Framework. "
                                   "Cite controls by AIR-* id and aigf:// resource URI.",
                      policy=SafetyPolicy(per_tool={"search_framework": RateLimit(calls=120)}))

def get_control(id: str, include_sections: bool = True) -> Control:
    """Return one AIGF control (mitigation) by id. Accepts AIR-PREV-020, mi-20, 20, or a title."""
    return catalog.resolve_control(id, include_sections)   # raises ToolError(ErrorEnvelope) on miss/ambiguity

register_tool(server, get_control, name="get_control", description=get_control.__doc__)

@server.resource("aigf://control/{id}", mime_type="text/markdown")
def control_markdown(id: str) -> str:
    return catalog.raw_markdown("control", id)

def main() -> None:
    server.run(transport="stdio")
```

### C. Test pattern (in-memory, no subprocess)

```python
import pytest
from mcp import Client
from finos_mcp.aigf.server import server

@pytest.fixture
def anyio_backend(): return "asyncio"

@pytest.fixture
async def client():
    async with Client(server, raise_exceptions=True) as c:
        yield c

@pytest.mark.anyio
async def test_get_control_by_public_id(client: Client):
    r = await client.call_tool("get_control", {"id": "AIR-PREV-020"})
    assert r.structured_content["short_id"] == "mi-20"
    assert "ri-26" not in r.structured_content["mitigates"]        # ids are AIR-* in output
    assert "AIR-SEC-026" in r.structured_content["mitigates"]

@pytest.mark.anyio
async def test_every_tool_is_read_only(client: Client):
    tools = await client.list_tools()
    assert all(t.annotations and t.annotations.read_only_hint for t in tools.tools)
```

### D. Retrieval eval core

```python
def recall_at_k(results: list[str], expected: set[str], k: int) -> float:
    return len(set(results[:k]) & expected) / len(expected)

@pytest.mark.anyio
async def test_retrieval(client, questions):
    scores = {1: [], 3: [], 5: []}; rr = []
    for q in questions:
        hits = (await client.call_tool("search_framework", {"query": q.question, "k": 10})).structured_content["result"]
        ids = [h["id"] for h in hits]
        for k in scores: scores[k].append(recall_at_k(ids, set(q.expected), k))
        rr.append(next((1/(i+1) for i, x in enumerate(ids) if x in q.expected), 0.0))
    metrics.record("retrieval", {f"recall_at_{k}": mean(v) for k, v in scores.items()} | {"mrr": mean(rr)})
    assert mean(scores[5]) >= 0.85
```

### E. Agent-in-the-loop core (preferred path)

```python
from anthropic import AsyncAnthropic
from anthropic.lib.tools.mcp import async_mcp_tool

async def run_task(task, mcp_client) -> AgentRun:
    client = AsyncAnthropic()
    tools = [async_mcp_tool(t, mcp_client) for t in (await mcp_client.list_tools()).tools]
    runner = client.beta.messages.tool_runner(
        model=os.environ.get("EVAL_MODEL", "claude-opus-5"), max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        system="Answer using the FINOS tools. Every control you mention must carry its AIR-* id "
               "and the aigf:// resource you read it from.",
        messages=[{"role": "user", "content": task.prompt}], tools=tools)
    called, final = [], None
    async for msg in runner:
        called += [b.name for b in msg.content if b.type == "tool_use"]
        final = msg
    assert final.stop_reason != "refusal", final.stop_details
    text = "".join(b.text for b in final.content if b.type == "text")
    return AgentRun(text=text, tools_called=called, cited=set(re.findall(r"AIR-(?:RC|OP|SEC|PREV|DET)-\d{3}", text)))
```

### F. What the README must say (verbatim commitments)

> **Safety model.** These servers are read-only. They contain no tool that writes to, posts to, or mutates any external system, file, or network endpoint. All framework content and schemas are vendored into the package at build time with recorded upstream commit hashes; the servers make no network calls at runtime. Every tool call is rate-limited per tool, input-capped, and written to an audit log. Any failure is returned as a structured error the calling agent can act on.
