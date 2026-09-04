"""Tests for `finos_mcp.cdm.registry`, checked against the vendored 7.2.0 drop.

These tests are deliberately about the *actual* content of `_vendor/`, not an
idealised one: PLAN.md 5.1/5.3 describe expected counts (~1136 schemas, 16 root
types, 35 qualify functions) which this file asserts against the real numbers
found by `sync_upstream.py`, and it records -- rather than hides -- the real
outcome of validating older-tag legacy samples against the 7.2.0 schema (see
`test_legacy_samples_validate_or_report_known_issues`).

`_vendor/` also carries a second, older JSON Schema vintage at
`_vendor/schemas-6.27.0/`, matching the vintage the vendored legacy-format
samples were pulled from. `CdmRegistry.schema_registry_for` exposes it
alongside the primary 7.2.0 registry; `test_legacy_samples_validate_against_matching_vintage_schema`
is the counterpart to `test_legacy_samples_validate_or_report_known_issues`
that actually exercises the legacy JSON Schema path meaningfully, same
vintage against same vintage, rather than only proving the vintage mismatch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft4Validator
from jsonschema.exceptions import UnknownType

from finos_mcp.cdm.registry import CdmRegistry
from finos_mcp.core import verify

VENDOR_DIR = Path(__file__).parents[1] / "src" / "finos_mcp" / "cdm" / "_vendor"
SCHEMAS_DIR = VENDOR_DIR / "schemas"
LEGACY_SCHEMA_VERSION = "6.27.0"
LEGACY_SCHEMAS_DIR = VENDOR_DIR / f"schemas-{LEGACY_SCHEMA_VERSION}"

EXPECTED_SCHEMA_COUNT = 1139
EXPECTED_ROOT_TYPE_COUNT = 16
EXPECTED_QUALIFY_COUNT = 35
EXPECTED_RUNE_SAMPLE_COUNT = 28
EXPECTED_LEGACY_SAMPLE_COUNT = 12
# cdm-json-schema-6.27.0.zip -- despite its name and the application/zip
# content-type Maven Central serves it with -- is actually a gzip-compressed
# tar archive (see sync_upstream.py's `_extract_schema_members`); it contains
# 1066 *.schema.json files. That is the real, counted number for this
# vendored snapshot, not an estimate.
EXPECTED_LEGACY_SCHEMA_COUNT = 1066
# How many of the 12 vendored legacy (6.27.0-tag) samples validate cleanly
# against the matching-vintage 6.27.0 `BusinessEvent` schema -- see
# `test_legacy_samples_validate_against_matching_vintage_schema`. Real,
# counted result: 5 valid, 7 invalid, 0 crashed. Every one of the 7 failures
# is a `required`-property miss (`activityDate`, `underlier`, `dateAdjustments`,
# `executionDetails`) at a nested path -- fields that became required only
# somewhere between 6.27.0 and 7.2.0 and so are genuinely absent from these
# older-tag sample documents; it is not a workaround-needed defect like the
# BusinessCenter/NonNegativeNumber one `_drop_bogus_type_keywords` handles.
EXPECTED_LEGACY_SAMPLES_VALID_AGAINST_OWN_VINTAGE = 5


@pytest.fixture(scope="module")
def registry() -> CdmRegistry:
    return CdmRegistry(VENDOR_DIR)


def _iter_refs(node: Any) -> Any:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            yield ref
        for value in node.values():
            yield from _iter_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_refs(item)


# -- vendoring / provenance --------------------------------------------------


def test_verify_passes() -> None:
    verify(VENDOR_DIR)


def test_schema_count() -> None:
    files = sorted(SCHEMAS_DIR.glob("*.schema.json"))
    assert len(files) == EXPECTED_SCHEMA_COUNT


def test_no_dangling_refs() -> None:
    """Walk every vendored schema (independent of CdmRegistry's own loading)
    and assert every `$ref` resolves to an existing sibling filename."""
    files = sorted(SCHEMAS_DIR.glob("*.schema.json"))
    filenames = {f.name for f in files}
    dangling: list[tuple[str, str]] = []
    for path in files:
        schema = json.loads(path.read_text(encoding="utf-8"), strict=False)
        for ref in _iter_refs(schema):
            if ref not in filenames:
                dangling.append((path.name, ref))
    assert dangling == [], f"{len(dangling)} dangling $ref(s): {dangling[:10]}"


def test_legacy_schema_count() -> None:
    """`_vendor/schemas-6.27.0/` is vendored alongside the primary 7.2.0 set
    (see `sync_upstream.py`) so legacy-format samples can be validated against
    a schema of matching vintage."""
    files = sorted(LEGACY_SCHEMAS_DIR.glob("*.schema.json"))
    assert len(files) == EXPECTED_LEGACY_SCHEMA_COUNT


def test_legacy_no_dangling_refs() -> None:
    """Same check as `test_no_dangling_refs`, against the vendored 6.27.0
    schema set."""
    files = sorted(LEGACY_SCHEMAS_DIR.glob("*.schema.json"))
    filenames = {f.name for f in files}
    dangling: list[tuple[str, str]] = []
    for path in files:
        schema = json.loads(path.read_text(encoding="utf-8"), strict=False)
        for ref in _iter_refs(schema):
            if ref not in filenames:
                dangling.append((path.name, ref))
    assert dangling == [], (
        f"{len(dangling)} dangling $ref(s) in {LEGACY_SCHEMA_VERSION}: {dangling[:10]}"
    )


# -- registry: types and fields ----------------------------------------------


def test_get_by_bare_name_and_fqn(registry: CdmRegistry) -> None:
    by_bare = registry.get("TradeState")
    by_fqn = registry.get("cdm.event.common.TradeState")
    by_fqn_ci = registry.get("CDM.EVENT.COMMON.tradestate")
    assert by_bare is not None
    assert by_bare == by_fqn == by_fqn_ci
    assert by_bare.namespace == "cdm.event.common"
    assert by_bare.root_type is True


def test_trade_required_fields(registry: CdmRegistry) -> None:
    trade = registry.get("Trade")
    assert trade is not None
    schema = json.loads((SCHEMAS_DIR / trade.filename).read_text(encoding="utf-8"), strict=False)
    assert schema.get("required") == ["tradeDate"]


def test_tradestate_required_fields(registry: CdmRegistry) -> None:
    trade_state = registry.get("TradeState")
    assert trade_state is not None
    schema = json.loads(
        (SCHEMAS_DIR / trade_state.filename).read_text(encoding="utf-8"), strict=False
    )
    assert schema.get("required") == ["trade"]


def test_fields_tradestate_includes_trade_1_1(registry: CdmRegistry) -> None:
    fields = {f.name: f for f in registry.fields("TradeState")}
    assert "trade" in fields
    assert fields["trade"].cardinality == "1..1"
    assert fields["trade"].type == "Trade"


def test_root_types(registry: CdmRegistry) -> None:
    root_types = registry.root_types()
    assert len(root_types) == EXPECTED_ROOT_TYPE_COUNT
    for expected in ("TradeState", "BusinessEvent", "WorkflowStep"):
        assert expected in root_types


def test_qualify_functions(registry: CdmRegistry) -> None:
    functions = registry.qualify_functions()
    assert len(functions) == EXPECTED_QUALIFY_COUNT
    names = {f.name for f in functions}
    assert "Qualify_Execution" in names
    assert "Qualify_Termination" in names
    for f in functions:
        assert f.has_business_event_annotation is True
        assert f.condition_text.startswith(("set is_event:", "condition"))


def test_used_by_tradestate_non_empty(registry: CdmRegistry) -> None:
    assert registry.used_by("TradeState") != []


# -- samples ------------------------------------------------------------------


def test_sample_counts(registry: CdmRegistry) -> None:
    samples = registry.samples()
    rune = [s for s in samples if s.format == "rune"]
    legacy = [s for s in samples if s.format == "legacy"]
    assert len(rune) == EXPECTED_RUNE_SAMPLE_COUNT
    assert len(legacy) == EXPECTED_LEGACY_SAMPLE_COUNT


def test_rune_samples_detected_as_rune(registry: CdmRegistry) -> None:
    """Every vendored Rune sample carries `@type` at the top level -- the
    detection signal the (separately-owned) dual validator will key off."""
    for sample in registry.samples():
        if sample.format != "rune":
            continue
        data = json.loads(Path(sample.path).read_text(encoding="utf-8"), strict=False)
        assert isinstance(data, dict)
        assert "@type" in data, f"{sample.name} missing top-level @type"
        assert sample.root_type_guess == data["@type"].rsplit(".", 1)[-1]


def test_legacy_samples_root_type_guess(registry: CdmRegistry) -> None:
    for sample in registry.samples():
        if sample.format == "legacy":
            assert sample.root_type_guess == "BusinessEvent"


def test_draft4validator_compiles_for_tradestate(registry: CdmRegistry) -> None:
    validator = registry.schema_registry.validator("cdm-event-common-TradeState.schema.json")
    assert isinstance(validator, Draft4Validator)


# -- multi-version schema registry --------------------------------------------


def test_schema_versions(registry: CdmRegistry) -> None:
    assert registry.schema_versions() == ["7.2.0", LEGACY_SCHEMA_VERSION]


def test_schema_registry_for_default_and_explicit_primary_are_the_primary_registry(
    registry: CdmRegistry,
) -> None:
    assert registry.schema_registry_for() is registry.schema_registry
    assert registry.schema_registry_for("7.2.0") is registry.schema_registry


def test_schema_registry_for_legacy_version(registry: CdmRegistry) -> None:
    sr = registry.schema_registry_for(LEGACY_SCHEMA_VERSION)
    assert sr.dialect == "draft4"
    assert len(sr) == EXPECTED_LEGACY_SCHEMA_COUNT
    # Cached: a second call returns the same instance rather than re-parsing.
    assert registry.schema_registry_for(LEGACY_SCHEMA_VERSION) is sr


def test_schema_registry_for_unknown_version_raises(registry: CdmRegistry) -> None:
    with pytest.raises(ValueError):
        registry.schema_registry_for("9.9.9")


def test_legacy_samples_validate_or_report_known_issues(registry: CdmRegistry) -> None:
    """Validate every vendored legacy (6.27.0) sample against the 7.2.0
    `BusinessEvent` schema and assert what is *actually* true of the vendored
    snapshot, rather than an assumed-clean result.

    Two real findings, surfaced here rather than swallowed:

    1. A handful of 7.2.0 schema files (`ValuationTime`, `CreditEventNotice`,
       ...) emit a literal Rosetta basictype name as a JSON Schema `"type"`
       keyword (`{"type": "BusinessCenter"}`, `{"type": "NonNegativeNumber"}`)
       instead of a JSON primitive or `$ref` -- a cdm-json-schema 7.2.0
       generator defect (confirmed: no `cdm-*-BusinessCenter.schema.json` or
       `cdm-*-NonNegativeNumber.schema.json` file exists). Left as-is, this
       hard-crashes `Draft4Validator` with `jsonschema.exceptions.UnknownType`
       the moment a real instance value reaches that property -- it crashed
       10 of the 12 vendored legacy samples outright before `CdmRegistry`
       worked around it (see `_drop_bogus_type_keywords`, which drops the
       bogus `type` keyword so the property is merely unconstrained rather
       than un-validatable). This test asserts that workaround holds: no
       sample may raise `UnknownType`.
    2. With that workaround in place, all 12 vendored legacy (6.27.0-tag)
       samples still fail *real* schema validation against the 7.2.0 schema
       -- **zero validate cleanly**. The dominant, recurring cause is that
       `priceQuantity[].quantity` is `array`-typed (`1..*`) in the 7.2.0
       schema but a bare object in the 6.27.0-tag sample shape; a smaller
       set of samples also hit newly-`required` fields
       (`activityDate`/`underlier`/`securityType`/`dateAdjustments`) that did
       not exist, or were not required, at 6.27.0. This is genuine structural
       drift between the two tags this vendoring pulls from (CDM's JSON shape
       evolved between 6.27.0 and 7.2.0 even before the 7.x Rune-format
       switch) -- not a bug in this registry. Anyone building the dual
       validator on top of `schema_registry` needs to know the legacy JSON
       Schema path only proves *shape*, and even that only for
       same-version-vintage documents.
    """
    sr = registry.schema_registry
    crashed: list[str] = []
    invalid: dict[str, list[str]] = {}
    valid: list[str] = []

    for sample in registry.samples():
        if sample.format != "legacy":
            continue
        data = json.loads(Path(sample.path).read_text(encoding="utf-8"), strict=False)
        try:
            report = sr.validate(data, "cdm-event-common-BusinessEvent.schema.json")
        except UnknownType:
            crashed.append(sample.name)
            continue
        if report.valid:
            valid.append(sample.name)
        else:
            invalid[sample.name] = [
                f"{issue.json_path} [{issue.kind}] {issue.message[:150]}"
                for issue in report.issues[:3]
            ]

    print(
        f"\nlegacy sample validation: {len(valid)} valid, {len(invalid)} invalid, {len(crashed)} crashed"
    )
    for name, issues in invalid.items():
        print(f"  INVALID {name}:")
        for issue in issues:
            print(f"    {issue}")
    for name in crashed:
        print(f"  CRASHED (UnknownType) {name}")

    # The BusinessCenter/NonNegativeNumber generator defect must never surface
    # as an uncaught crash once CdmRegistry's workaround is in place.
    assert crashed == [], f"UnknownType workaround regressed for: {crashed}"
    assert len(valid) + len(invalid) == EXPECTED_LEGACY_SAMPLE_COUNT

    # The actual, current truth for this vendored snapshot (see docstring):
    # every legacy sample carries at least one real schema mismatch against
    # the newer 7.2.0 schema, so none validate cleanly.
    assert len(valid) == 0
    assert len(invalid) == EXPECTED_LEGACY_SAMPLE_COUNT
    for issues in invalid.values():
        assert issues, "expected at least one reported issue for an invalid sample"


def test_legacy_samples_validate_against_matching_vintage_schema(registry: CdmRegistry) -> None:
    """Validate every vendored legacy sample against the *matching-vintage*
    6.27.0 `BusinessEvent` schema (`registry.schema_registry_for("6.27.0")`),
    in contrast to `test_legacy_samples_validate_or_report_known_issues` above,
    which deliberately validates the same samples against the newer 7.2.0
    schema and documents that none validate cleanly there.

    This is the check that makes the legacy JSON Schema path meaningful: it
    only ever proves *shape*, and only for documents of the same vintage as
    the schema. Validating 6.27.0-tag samples against a 6.27.0 schema
    exercises that guarantee for real, rather than against a schema that is
    already known (see above) to have drifted structurally.
    """
    sr = registry.schema_registry_for(LEGACY_SCHEMA_VERSION)
    crashed: list[str] = []
    invalid: dict[str, list[str]] = {}
    valid: list[str] = []

    for sample in registry.samples():
        if sample.format != "legacy":
            continue
        data = json.loads(Path(sample.path).read_text(encoding="utf-8"), strict=False)
        try:
            report = sr.validate(data, "cdm-event-common-BusinessEvent.schema.json")
        except UnknownType:
            crashed.append(sample.name)
            continue
        if report.valid:
            valid.append(sample.name)
        else:
            invalid[sample.name] = [
                f"{issue.json_path} [{issue.kind}] {issue.message[:150]}"
                for issue in report.issues[:3]
            ]

    print(
        f"\nlegacy sample validation against matching {LEGACY_SCHEMA_VERSION} schema: "
        f"{len(valid)} valid, {len(invalid)} invalid, {len(crashed)} crashed"
    )
    for name, issues in invalid.items():
        print(f"  INVALID {name}:")
        for issue in issues:
            print(f"    {issue}")
    for name in crashed:
        print(f"  CRASHED (UnknownType) {name}")

    assert crashed == [], (
        f"UnknownType workaround needed for {LEGACY_SCHEMA_VERSION} schema too: {crashed}"
    )
    assert len(valid) + len(invalid) == EXPECTED_LEGACY_SAMPLE_COUNT
    for issues in invalid.values():
        assert issues, "expected at least one reported issue for an invalid sample"

    # The actual, current truth for this vendored snapshot: see the report
    # printed above (`pytest -s`) for the real per-sample issue lists this
    # asserts against.
    assert len(valid) == EXPECTED_LEGACY_SAMPLES_VALID_AGAINST_OWN_VINTAGE
    assert (
        len(invalid)
        == EXPECTED_LEGACY_SAMPLE_COUNT - EXPECTED_LEGACY_SAMPLES_VALID_AGAINST_OWN_VINTAGE
    )


def test_hand_mutated_sample_missing_required_field_reports_required_kind(
    registry: CdmRegistry,
) -> None:
    """Take a real vendored legacy sample's `after[0]` TradeState fragment,
    delete its required `trade` field, and confirm the issue is reported with
    `kind == "required"` at the right path."""
    legacy = next(s for s in registry.samples() if s.format == "legacy")
    data = json.loads(Path(legacy.path).read_text(encoding="utf-8"), strict=False)
    trade_state = data["after"][0]
    assert "trade" in trade_state
    del trade_state["trade"]

    report = registry.schema_registry.validate(
        trade_state, "cdm-event-common-TradeState.schema.json"
    )
    assert not report.valid
    assert any(issue.kind == "required" for issue in report.issues)
    required_issues = [issue for issue in report.issues if issue.kind == "required"]
    assert any("trade" in issue.message for issue in required_issues)
