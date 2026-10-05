"""The CDM release check: pure logic only, no network."""

from __future__ import annotations

from pathlib import Path

from finos_mcp_evals.cdm_release_check import (
    newer_releases,
    report,
    stable_versions,
    vendored_versions,
)

METADATA = """<metadata><versioning><versions>
<version>0.0.0-test.1</version>
<version>6.27.0</version><version>6.28.1</version><version>6.29.0</version>
<version>7.0.0-dev.3</version><version>7.2.0</version><version>7.4.0</version>
<version>7.10.0</version>
<version>8.0.0-dev.8</version>
</versions></versioning></metadata>"""


def test_stable_versions_ignore_prereleases_and_sort_numerically() -> None:
    assert stable_versions(METADATA) == ["6.27.0", "6.28.1", "6.29.0", "7.2.0", "7.4.0", "7.10.0"]


def test_reports_the_newest_release_in_each_vendored_line() -> None:
    published = stable_versions(METADATA)
    # 7.10.0 > 7.4.0 numerically, although "7.10.0" < "7.4.0" as text
    assert newer_releases(["6.29.0", "7.4.0"], published) == [("7.4.0", "7.10.0")]
    assert newer_releases(["6.27.0", "7.10.0"], published) == [("6.27.0", "6.29.0")]
    assert newer_releases(["6.29.0", "7.10.0"], published) == []


def test_reports_a_new_major_line_only_once_it_has_a_stable_release() -> None:
    published = stable_versions(METADATA)
    assert all(latest != "8.0.0-dev.8" for _, latest in newer_releases(["7.10.0"], published))
    with_eight = [*published, "8.0.0", "8.1.0"]
    assert ("none", "8.1.0") in newer_releases(["6.29.0", "7.10.0"], with_eight)


def test_vendored_versions_come_from_the_bundle_files(tmp_path: Path) -> None:
    for name in ("cdm-json-schema-7.4.0.json", "cdm-json-schema-6.29.0.json", "notes.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    assert vendored_versions(tmp_path) == ["6.29.0", "7.4.0"]


def test_this_repository_vendors_two_cdm_versions() -> None:
    import finos_mcp.cdm

    schemas = Path(finos_mcp.cdm.__file__ or "").parent / "_vendor" / "schemas"
    assert len(vendored_versions(schemas)) == 2


def test_report_says_what_to_do() -> None:
    text = report(["6.29.0", "7.4.0"], [("7.4.0", "7.5.0")])
    assert "**7.5.0** is newer than the vendored 7.4.0" in text and "PRIMARY_VERSION" in text
    assert "No newer stable CDM release" in report(["6.29.0", "7.4.0"], [])
