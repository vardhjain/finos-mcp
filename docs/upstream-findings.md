# Upstream findings

Defects and surprises in the FINOS sources discovered while vendoring them, verified on
2026-09-04. Each is a candidate issue or pull request against the upstream project; the
finos-mcp servers work around every one of them and pin the current behaviour in tests so
an upstream fix shows up as a test diff on the next sync.

## AI Governance Framework (finos/ai-governance-framework)

1. **Seven risk files lose their `related_risks` list to a YAML comment.** In
   `docs/_risks/` the last `uk-regulations_references` entry's inline `# comment` has no
   newline before the following `related_risks:` key, so YAML folds the key into the comment
   and the stray `ri-N` tokens land in `uk-regulations_references` as bogus reference keys
   (19 unresolvable references). Files: the seven risks whose parser test entry lists
   `uk-regulations` keys of the form `ri-N`. Fix: a newline. Pinned in
   `servers/aigf/tests/test_parser.py` as `EXPECTED_UNRESOLVED_REFS`.
2. `docs/_data/references/` holds 13 datasets plus a `README.md`; documentation elsewhere
   counts 14.

## Common Domain Model (finos/common-domain-model, Maven `cdm-json-schema`)

3. **Rosetta basic-type names leak into JSON Schema `type`.** Eight 7.2.0 schema files emit
   `{"type": "BusinessCenter"}` or `{"type": "NonNegativeNumber"}`, which are not JSON
   Schema types and no schema file defines them; a strict Draft 4 validator raises
   `UnknownType`. Worked around at load time by dropping the bogus keyword. Generator:
   REGnosys/rosetta-code-generators `json-schema`.
4. **Two 7.2.0 enum schema files contain raw control characters** in descriptions
   (`cdm-legaldocumentation-csa-CollateralAssetDefinitionsEnum`,
   `cdm-product-collateral-RatingPriorityResolutionEnum`); strict JSON parsers reject them.
5. **Non-standard `$anchor` at the top level** of every schema file (used to carry the
   namespace). Harmless to Draft 4 but stripped for cleanliness.
6. **The published schema and the published samples disagree on required fields.** Against
   cdm-json-schema 7.2.0, 18 of 28 official 7.2.0 `*-func-output.json` samples fail only on
   `required` (`ClosedState.activityDate`, `executionDetails`, `underlier`,
   `dateAdjustments`, `exerciseNoticeGiver`). Either the schema over-declares cardinality
   relative to the Rune source, or the samples are not fully populated. Pinned in
   `servers/cdm/tests/test_server.py` (`EXPECTED_VALID`, `EXPECTED_REQUIRED_MISSES`).
7. **`cdm-json-schema-6.27.0.zip` on Maven Central is a gzipped tar**, not a zip, despite the
   extension and `application/zip` content type. The sync script detects the magic bytes.
8. **The JSON Schema models the legacy JSON shape only.** CDM 7 documents use the Rune JSON
   shape (`@type`, `@key`, `@ref`, `@scheme`/`@data`) and cannot be validated with the
   published schema as-is. finos-mcp normalises Rune JSON into the legacy shape, directed by
   the schema, before validating. A Rune-shape JSON Schema would remove the need.
9. **`finos-cdm` 7.2.0 on PyPI is not usable as a validator.** Importing a model module
   directly raises a circular `ImportError` through the lazy `finos._bundle`; importing the
   bundle first takes about four minutes on a warm cache; and `BusinessEvent.rune_deserialize`
   then rejects CDM's own 7.2.0 samples with `Input should be None` on typed fields
   (`instruction[].primitiveInstruction.split`, `after[].trade`), which suggests field
   annotations resolve to `None` in the generated models. finos-mcp therefore does not depend
   on it.
10. **One legacy 6.27.0 sample contains a raw control character** and needs lenient JSON
    parsing.

## FDC3 (finos/FDC3)

11. **The intent-to-context mapping is not machine-readable.** It exists only as
    `## Possible Contexts` bullet lists in `website/docs/intents/ref/*.md`; `Intents.ts` and
    `standard intents.json` carry names only. finos-mcp generates `intents.json` from the
    markdown with a drift test. A checked-in JSON table upstream would help every consumer.
12. **`fdc3.action` references the API schema package.** `action.schema.json` `$ref`s
    `../api/api.schema.json#/definitions/AppIdentifier`, so the context schemas are not
    self-contained; validating an `fdc3.action` needs the API schemas too. Reported as a
    structured `reference` issue.
13. **`security.user.schema.json` has an `$id` ending in `user.schema.json`**, unlike every
    other file whose `$id` matches its filename (main branch only).
14. Public claims that FDC3 3.0 "adds MCP integration" are not reflected in the repository or
    the 3.0 announcement; 3.0 is at `3.0.0-alpha.2`.
