from __future__ import annotations

import json
from pathlib import Path

import pytest
from generate_intents import generate

from finos_mcp.core import verify
from finos_mcp.fdc3 import Fdc3Registry, get_registry

VENDOR_DIR = Path(__file__).resolve().parents[1] / "src" / "finos_mcp" / "fdc3" / "_vendor"

# `fdc3.action`'s `app` property `$ref`s `../api/api.schema.json#/definitions/AppIdentifier`,
# which lives in the FDC3 *API/wire* schema package (`packages/fdc3-schema/schemas/api/`)
# -- deliberately out of scope for this server, which vendors only the *context* schemas
# (PLAN.md 1.3/6.2). That makes `fdc3.action`'s own bundled example -- which includes an
# `app` value -- the one context type whose example cannot be validated end to end.
EXPECTED_UNRESOLVABLE_EXAMPLES = {"fdc3.action"}


@pytest.fixture(scope="module")
def registry() -> Fdc3Registry:
    return get_registry()


def test_vendor_integrity_passes() -> None:
    verify(VENDOR_DIR)


def test_schema_count_is_29_at_v2_2_3(registry: Fdc3Registry) -> None:
    # 28 named context types (`type` const) + the base `context.schema.json` they all
    # `$ref`, matching the 29-file 2.2.3 tarball noted in PLAN.md 1.3.
    assert registry.counts()["schemas"] == 29
    assert len(registry.context_types()) == 28


def test_every_context_ref_resolves_except_the_known_out_of_scope_one(
    registry: Fdc3Registry,
) -> None:
    unresolved: set[str] = set()
    for ct in registry.context_types():
        example = registry.example_for(ct.type)
        assert example is not None, f"{ct.type} has no bundled example"
        report = registry.validate_context(example, type=ct.type)
        if not report.valid and any(issue.kind == "reference" for issue in report.issues):
            unresolved.add(ct.type)
    assert unresolved == EXPECTED_UNRESOLVABLE_EXAMPLES


def test_every_intent_has_at_least_one_context(registry: Fdc3Registry) -> None:
    empty = [intent.name for intent in registry.intents() if not intent.contexts]
    # On the vendored v2.2.3 snapshot every intent lists at least one possible context.
    assert empty == []


def test_every_context_referenced_by_an_intent_is_a_known_type(registry: Fdc3Registry) -> None:
    known = {ct.type for ct in registry.context_types()}
    for intent in registry.intents():
        for context_type in intent.contexts:
            assert context_type in known, (
                f"{intent.name} references unknown context type {context_type!r}"
            )
        if intent.result is not None:
            assert intent.result in known, (
                f"{intent.name} declares unknown result type {intent.result!r}"
            )


def test_view_chart_contexts_sorted(registry: Fdc3Registry) -> None:
    intent = registry.get_intent("ViewChart")
    assert intent is not None
    assert intent.contexts == sorted(
        ["fdc3.chart", "fdc3.instrument", "fdc3.instrumentList", "fdc3.portfolio", "fdc3.position"]
    )


def test_intents_for_instrument_context(registry: Fdc3Registry) -> None:
    names = {intent.name for intent in registry.intents_for_context("fdc3.instrument")}
    for expected in ("ViewInstrument", "ViewChart", "ViewQuote", "ViewNews"):
        assert expected in names
    # Full expected set at v2.2.3 (also the DoD list for the eventual `suggest_intent`
    # tool in PLAN.md 6.5) -- pinned so upstream doc drift is a visible diff.
    assert names == {
        "ViewAnalysis",
        "ViewChart",
        "ViewHoldings",
        "ViewInstrument",
        "ViewInteractions",
        "ViewNews",
        "ViewOrders",
        "ViewQuote",
        "ViewResearch",
    }


def test_view_contact_is_deprecated(registry: Fdc3Registry) -> None:
    intent = registry.get_intent("ViewContact")
    assert intent is not None
    assert intent.deprecated is True


def test_intent_count_is_19_standard_at_v2_2_3(registry: Fdc3Registry) -> None:
    intents = registry.intents()
    assert len(intents) == 19
    assert registry.counts()["intents"] == 19
    assert all(intent.standard for intent in intents)


def test_get_intent_is_case_insensitive(registry: Fdc3Registry) -> None:
    assert registry.get_intent("viewchart") is registry.get_intent("ViewChart")
    assert registry.get_intent("VIEWCHART") is not None
    assert registry.get_intent("NoSuchIntent") is None


def test_get_context_accepts_type_bare_name_and_title(registry: Fdc3Registry) -> None:
    by_type = registry.get_context("fdc3.instrument")
    by_bare = registry.get_context("instrument")
    by_title = registry.get_context("Instrument")
    assert by_type is by_bare is by_title
    assert by_type is not None
    assert by_type.type == "fdc3.instrument"


def test_every_schema_example_validates_except_the_known_exception(
    registry: Fdc3Registry,
) -> None:
    failing: set[str] = set()
    for ct in registry.context_types():
        example = registry.example_for(ct.type)
        assert example is not None
        report = registry.validate_context(example, type=ct.type)
        if not report.valid:
            failing.add(ct.type)
    assert failing == EXPECTED_UNRESOLVABLE_EXAMPLES


def test_mutated_example_type_is_invalid(registry: Fdc3Registry) -> None:
    example = registry.example_for("fdc3.instrument")
    assert example is not None
    mutated = dict(example)
    mutated["type"] = "fdc3.nope"
    report = registry.validate_context(mutated, type="fdc3.instrument")
    assert not report.valid
    assert report.issues


def test_minimal_instrument_is_valid(registry: Fdc3Registry) -> None:
    report = registry.validate_context({"type": "fdc3.instrument", "id": {"ticker": "AAPL"}})
    assert report.valid, report.issues


def test_instrument_extra_top_level_property_is_not_rejected(registry: Fdc3Registry) -> None:
    """`instrument.schema.json` has no top-level `unevaluatedProperties`/`additionalProperties:
    false` (that keyword only appears nested, constraining the `id`/`market` sub-objects to
    string-valued properties -- see PLAN.md 1.3/6.2 and the vendored schema itself). An extra,
    unrelated top-level property is therefore valid, not rejected -- unlike CDM's stricter
    schemas. This test pins that observed (permissive) behaviour.
    """
    obj = {
        "type": "fdc3.instrument",
        "id": {"ticker": "AAPL"},
        "unknownTopLevelField": "anything",
    }
    report = registry.validate_context(obj)
    assert report.valid, report.issues


def test_unknown_context_type_reports_a_type_issue(registry: Fdc3Registry) -> None:
    report = registry.validate_context({"type": "fdc3.nope"})
    assert not report.valid
    assert len(report.issues) == 1
    assert report.issues[0].kind == "type"
    assert report.issues[0].message == "unknown context type"


def test_validate_context_defaults_type_from_object() -> None:
    registry = get_registry()
    report = registry.validate_context({"type": "fdc3.contact", "id": {"email": "a@b.com"}})
    assert report.valid, report.issues


def test_intents_json_matches_regenerated_output() -> None:
    """Drift test: the checked-in `_vendor/intents.json` must equal a fresh `generate()`.

    Upstream prose can change shape without notice, so the checked-in JSON -- not the
    generator -- is the runtime source of truth; a diff here means a human should review
    and re-run `scripts/sync_upstream.py` deliberately rather than silently reflect drift.
    """
    regenerated = generate(VENDOR_DIR)
    checked_in = json.loads((VENDOR_DIR / "intents.json").read_text(encoding="utf-8"))
    assert regenerated == checked_in
