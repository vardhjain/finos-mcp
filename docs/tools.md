# Tool reference

Generated from the live servers by `uv run python -m finos_mcp_evals.toolref`. Every tool is read-only, returns typed `structuredContent` described by its `outputSchema`, and raises structured errors (`not_found`, `ambiguous_id`, `invalid_input`, ...) the calling agent can act on.

## finos-mcp-aigf

FINOS AI Governance Framework v2 — upstream `finos/ai-governance-framework@main` (7728f9512160). Exposes: controls=23, crosswalk_refs=765, reference_entries=957, reference_frameworks=13, risk_control_edges=88, risks=23.

### Tools

| Tool | Arguments (`*` required) | Description |
|---|---|---|
| `find_by_external_reference` | `key`*: string, `framework`: string/null | Reverse crosswalk: find the AIGF risks and controls that cite an external reference, e.g. key='sa-9' (NIST SP 800-53), 'llm01-2025' (OWASP LLM Top 10), 'c3-s2-a15' (EU AI Act), 'A-6-2-6' (ISO 42001). Matching is case-insensitive and ignores punctuation; optionally restrict to one framework name from list_reference_frameworks. |
| `get_control` | `id`*: string, `include_sections`: boolean | Get one AIGF control by id (AIR-PREV-020, mi-20, 20, or its title), with the risks it mitigates, related controls, and crosswalk references (NIST SP 800-53, ISO 42001, ...). Set include_sections=false for a compact record. |
| `get_risk` | `id`*: string, `include_sections`: boolean | Get one AIGF risk by id (AIR-SEC-010, ri-10, 10, or its title), with the controls that mitigate it, related risks, and external references. Set include_sections=false for a compact record without the full text. |
| `list_controls` | `type`: string/null, `status`: string/null, `page`: integer, `page_size`: integer | List AIGF controls (the framework calls them mitigations). Filter by type (PREV = preventative, DET = detective) or status. Returns ids for get_control. |
| `list_reference_frameworks` | - | List the external reference frameworks the AIGF crosswalks to, with entry counts and how many risks and controls cite each. |
| `list_risks` | `type`: string/null, `status`: string/null, `page`: integer, `page_size`: integer | List AIGF risks. Filter by type (RC = regulatory and compliance, OP = operational, SEC = security) or document status. Returns ids you can pass to get_risk. |
| `map_control_to_external` | `id`*: string, `frameworks`: array/null | Crosswalk one control to external frameworks: NIST SP 800-53 r5, NIST AI 600-1, ISO 42001, EU AI Act, OWASP LLM/ML/ASI, FFIEC, IOSCO, SR 11-7 and others. Optionally restrict to the named frameworks (see list_reference_frameworks). |
| `map_risks_to_controls` | `risk_ids`: array/null, `query`: string/null, `queries`: array/null, `k`: integer, `control_type`: string/null | Map risks to the controls that mitigate them. Pass explicit risk_ids (up to 25), a free-text query (the top k matching risks are used), and/or up to 5 queries (each contributing its own top k matches, unioned with everything else) -- useful for "both X and Y" questions where a single query blurs together two distinct concepts. Controls are ordered by how many of the given risks they cover; control_type (PREV or DET) restricts the result. Reports uncovered risks and any inputs that did not resolve. |
| `search_framework` | `query`*: string, `scope`: string, `k`: integer | Full-text search over risks and controls. Each hit has an id, the matching section, a snippet, and an aigf:// citation URI. Use scope to limit to risks or controls. |
| `search_status` | - | Report search_framework's active retrieval mode: whether it is BM25-only (lexical) or fused with dense semantic search (hybrid), and why -- e.g. the `semantic` extra is not installed, or a model failed to load. |
| `server_info` | - | Describe this server: standard version, upstream provenance, exposed counts, latency, policy. |

### Resources

| URI | Title | MIME |
|---|---|---|
| `aigf://risk/{id}` | AIGF risk (raw markdown) | text/markdown |
| `aigf://control/{id}` | AIGF control (raw markdown) | text/markdown |
| `aigf://risk/{id}/section/{slug}` | One section of an AIGF risk | text/markdown |
| `aigf://control/{id}/section/{slug}` | One section of an AIGF control | text/markdown |
| `aigf://reference/{framework}` | External reference dataset | application/json |
| `aigf://index` | Catalog index of all risks and controls | application/json |

### Prompts

- `assess_use_case`(`description`): Identify applicable AIGF risks and the controls that mitigate each, citing ids.
- `control_gap_analysis`(`controls_in_place`): Given controls in place, find risks left uncovered and suggest controls.

## finos-mcp-cdm

FINOS Common Domain Model 7.2.0 — upstream `finos/common-domain-model@7.2.0` (c38016efca75). Exposes: choice_types=16, enums=279, qualify_functions=35, root_types=16, samples=40, schemas=1139, schemas_legacy_vintage=1066, types=764.

### Tools

| Tool | Arguments (`*` required) | Description |
|---|---|---|
| `describe_type` | `name`*: string | Describe one CDM type by name (TradeState) or fully qualified name (cdm.event.common.TradeState): every field with its type and cardinality, choice alternatives, which types reference it, and the schema resource to cite. |
| `explain_event` | `event`: object/null, `qualifier`: string/null | Explain a CDM BusinessEvent. Pass the event JSON to read its qualifier, instruction kinds, before/after trade states and the products involved; or pass a qualifier name (Execution, Termination, ...) to get the Qualify_* rule from the CDM sources and a sample that exercises it. |
| `get_sample` | `name`*: string | Fetch one vendored sample document by name (see list_samples), e.g. a Rune-format Execution BusinessEvent for an interest-rate swap, to use as a template. |
| `list_products` | - | Catalogue of product types: the product template types (NonTransferableProduct, TransferableProduct, TradableProduct, EconomicTerms, Payout) and every Payout alternative (InterestRatePayout, CreditDefaultPayout, OptionPayout, ...), with the vendored samples that use each. |
| `list_samples` | `format`: string/null | List the vendored sample documents (Rune-format from CDM 7.2.0, legacy from 6.27.0). |
| `list_types` | `namespace`: string/null, `kind`: string/null, `root_only`: boolean, `page`: integer, `page_size`: integer | List CDM types. Filter by namespace prefix (cdm.product), kind (type, enum, choice, meta) or root types only (the 16 top-level document types such as TradeState). |
| `search_types` | `query`*: string, `k`: integer | Keyword search over CDM type names and descriptions (e.g. 'floating rate payout'). |
| `server_info` | - | Describe this server: standard version, upstream provenance, exposed counts, latency, policy. |
| `validate_object` | `object`*: object, `type`: string/null, `format`: string, `schema_version`: string/null | Validate a CDM JSON object against the published schema. The format (Rune with '@type'/'@key'/'@ref' keys, or legacy 'value'/'meta' wrappers) is detected unless given. The type comes from '@type' or the type argument (e.g. TradeState). Use schema_version='6.27.0' for legacy documents produced by CDM 6. Every issue carries the JSON path in your document and a kind (required, cardinality, type, enum, ...). |

### Resources

| URI | Title | MIME |
|---|---|---|
| `cdm://schema/{type_name}` | CDM JSON Schema for one type | application/schema+json |
| `cdm://sample/{name}` | Vendored CDM sample document | application/json |
| `cdm://qualify/{name}` | Event qualification rule (Rune source excerpt) | text/plain |
| `cdm://index` | Index of root types, qualifiers, samples and schema versions | application/json |

## finos-mcp-fdc3

FINOS FDC3 2.2.3 — upstream `finos/FDC3@v2.2.3` (0d71e7fb1b7a). Exposes: context_types=28, intents=19, schemas=29.

### Tools

| Tool | Arguments (`*` required) | Description |
|---|---|---|
| `find_intents_by_context` | `context_type`*: string | FDC3-API-style alias of list_intents(context_type=...): the intents that accept a context type. |
| `get_context_schema` | `type`*: string | Get the JSON Schema for a context type (by type such as fdc3.instrument, or by name such as Instrument), with a summary of required and optional properties and the standard example. |
| `get_intent` | `name`*: string | Get one intent by name (case-insensitive): accepted contexts, result type, description, deprecation status, and the fdc3:// resource holding its reference documentation. |
| `list_context_types` | `experimental`: boolean/null | List the FDC3 context types (fdc3.instrument, fdc3.contact, ...), whether each is experimental, and which intents accept it. |
| `list_intents` | `include_deprecated`: boolean, `context_type`: string/null | List the standard FDC3 intents with the context types each accepts and the result type it returns, if any. Filter to intents that accept one context_type (e.g. fdc3.instrument). |
| `search_intents` | `query`*: string, `k`: integer | Keyword search over intent names and descriptions. |
| `server_info` | - | Describe this server: standard version, upstream provenance, exposed counts, latency, policy. |
| `suggest_intent` | `context`: object/null, `context_type`: string/null, `goal`: string/null | Suggest which intents to raise for a context. Pass the context object (its `type` is used; if missing or unknown the object is matched structurally against every schema), or a context_type. An optional goal ("show a price chart") re-ranks by description. |
| `validate_context` | `context`*: object, `type`: string/null | Validate a context object against its FDC3 schema. The type is read from the object's `type` field unless given explicitly. Issues carry a JSON path and a kind (required, type, enum, unknown_field, ...). |

### Resources

| URI | Title | MIME |
|---|---|---|
| `fdc3://schema/{type}` | FDC3 context schema (raw JSON Schema) | application/schema+json |
| `fdc3://intent/{name}` | FDC3 intent reference documentation (raw markdown) | text/markdown |
| `fdc3://intents` | Generated intent-to-context table | application/json |
| `fdc3://index` | Index of context types and intents | application/json |
