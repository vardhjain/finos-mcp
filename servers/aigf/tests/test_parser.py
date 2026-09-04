from __future__ import annotations

from pathlib import Path

import pytest

from finos_mcp.aigf.parser import framework_documents, load_framework
from finos_mcp.aigf.models import Framework
from finos_mcp.core import verify

VENDOR_DIR = Path(__file__).parents[1] / "src" / "finos_mcp" / "aigf" / "_vendor"

# A handful of upstream risk files have a missing newline between the last
# uk-regulations_references comment and a following `related_risks:` key, which
# folds that key into the YAML comment and leaves stray `ri-N` tokens inside
# uk-regulations_references (see parser.py module docstring). Those tokens do not
# exist in the uk-regulations dataset and are the only unresolved reference keys
# on the currently vendored snapshot.
EXPECTED_UNRESOLVED_REFS = {
    ("AIR-OP-016", "uk-regulations", "ri-19"),
    ("AIR-OP-016", "uk-regulations", "ri-22"),
    ("AIR-OP-017", "uk-regulations", "ri-22"),
    ("AIR-OP-017", "uk-regulations", "ri-16"),
    ("AIR-OP-017", "uk-regulations", "ri-18"),
    ("AIR-OP-018", "uk-regulations", "ri-10"),
    ("AIR-OP-018", "uk-regulations", "ri-17"),
    ("AIR-OP-018", "uk-regulations", "ri-22"),
    ("AIR-OP-019", "uk-regulations", "ri-4"),
    ("AIR-OP-019", "uk-regulations", "ri-16"),
    ("AIR-OP-019", "uk-regulations", "ri-9"),
    ("AIR-RC-001", "uk-regulations", "ri-2"),
    ("AIR-RC-001", "uk-regulations", "ri-23"),
    ("AIR-OP-020", "uk-regulations", "ri-10"),
    ("AIR-OP-020", "uk-regulations", "ri-16"),
    ("AIR-OP-020", "uk-regulations", "ri-4"),
    ("AIR-RC-022", "uk-regulations", "ri-16"),
    ("AIR-RC-022", "uk-regulations", "ri-17"),
    ("AIR-RC-022", "uk-regulations", "ri-18"),
}


@pytest.fixture(scope="module")
def framework() -> Framework:
    return load_framework()


def test_vendor_integrity_passes() -> None:
    verify(VENDOR_DIR)


def test_exactly_23_risks_and_23_controls(framework: Framework) -> None:
    assert len(framework.risks) == 23
    assert len(framework.controls) == 23


def test_ri10_is_prompt_injection(framework: Framework) -> None:
    risk = framework.risks["AIR-SEC-010"]
    assert risk.short_id == "ri-10"
    assert risk.title == "Prompt Injection"
    assert risk.type == "SEC"
    assert risk.id == "AIR-SEC-010"


def test_mi20_mitigates_expected_risks(framework: Framework) -> None:
    control = framework.controls["AIR-PREV-020"]
    assert control.short_id == "mi-20"
    assert control.type == "PREV"
    # ri-26 (SEC), ri-8 (SEC), ri-1 (RC) per mi-20's frontmatter `mitigates:` list.
    assert set(control.mitigates) == {"AIR-SEC-026", "AIR-SEC-008", "AIR-RC-001"}


def test_every_cross_reference_id_exists_in_framework(framework: Framework) -> None:
    all_ids = set(framework.risks) | set(framework.controls)
    for risk in framework.risks.values():
        for ref_id in [*risk.related_risks, *risk.mitigated_by]:
            assert ref_id in all_ids, f"{risk.id} references unknown id {ref_id!r}"
    for control in framework.controls.values():
        for ref_id in [*control.mitigates, *control.related_controls]:
            assert ref_id in all_ids, f"{control.id} references unknown id {ref_id!r}"


def test_every_external_ref_framework_has_a_dataset(framework: Framework) -> None:
    for record in [*framework.risks.values(), *framework.controls.values()]:
        for ref in record.references:
            assert ref.framework in framework.references, (
                f"{record.id} cites unknown reference framework {ref.framework!r}"
            )


def test_external_ref_resolution_rate_at_least_95_percent(framework: Framework) -> None:
    total = 0
    unresolved: set[tuple[str, str, str]] = set()
    for record in [*framework.risks.values(), *framework.controls.values()]:
        for ref in record.references:
            total += 1
            if ref.title is None:
                unresolved.add((record.id, ref.framework, ref.key))
    assert total > 0
    resolved_rate = (total - len(unresolved)) / total
    assert resolved_rate >= 0.95, f"only {resolved_rate:.2%} of refs resolved; unresolved={sorted(unresolved)}"
    # Pin the exact unresolved set so upstream drift (fixed or new) is a visible diff.
    assert unresolved == EXPECTED_UNRESOLVED_REFS


def test_every_risk_has_at_least_one_mitigated_by(framework: Framework) -> None:
    unmitigated = [risk.id for risk in framework.risks.values() if not risk.mitigated_by]
    # On the currently vendored snapshot every risk is mitigated by at least one
    # control; if upstream adds an unmitigated risk this assertion documents it.
    assert unmitigated == []


def test_framework_version_matches_config(framework: Framework) -> None:
    import yaml

    config = yaml.safe_load((VENDOR_DIR / "_config.yml").read_text(encoding="utf-8"))
    assert framework.version == str(config["version"])


def test_framework_documents_aliases_include_short_ids(framework: Framework) -> None:
    risk_docs, control_docs = framework_documents(framework)
    assert len(risk_docs) == 23
    assert len(control_docs) == 23

    risk10 = next(d for d in risk_docs if d.id == "AIR-SEC-010")
    assert "ri-10" in risk10.aliases
    assert "10" in risk10.aliases
    assert risk10.kind == "risk"

    control20 = next(d for d in control_docs if d.id == "AIR-PREV-020")
    assert "mi-20" in control20.aliases
    assert "20" in control20.aliases
    assert control20.kind == "control"

    for doc in [*risk_docs, *control_docs]:
        short_id = doc.meta.get("type")
        assert short_id is not None
        assert doc.meta.get("status") is not None
