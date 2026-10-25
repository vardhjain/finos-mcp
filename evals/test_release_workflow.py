"""Fail-closed publication gates and curated release notes are required.

Static GitHub Actions policy checks; no network, tokens or tag creation.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _release_workflow() -> dict[str, object]:
    # BaseLoader preserves the literal GitHub Actions 'on' key (YAML 1.1
    # SafeLoader incorrectly coerces 'on' to Boolean True).
    value = yaml.load(
        (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert isinstance(value, dict)
    return value


def test_public_release_waits_for_pypi_and_rejects_partial_uploads() -> None:
    jobs = _release_workflow()["jobs"]
    release = jobs["github-release"]
    assert set(release["needs"]) == {"build", "publish-pypi"}
    guard = release["if"]
    assert "needs.build.result == 'success'" in guard
    assert "needs.publish-pypi.result == 'success'" in guard
    assert "vars.PUBLISH_TO_PYPI != 'true'" in guard
    assert "vars.PYPI_SKIP_PACKAGES == ''" in guard
    assert "!cancelled()" in guard

    # All four packages must be present in the publication matrix.
    matrix = jobs["publish-pypi"]["strategy"]["matrix"]["include"]
    assert {row["package"] for row in matrix} == {"core", "aigf", "cdm", "fdc3"}


def test_announcement_uses_reviewed_tag_release_notes() -> None:
    data = _release_workflow()
    assert "workflow_dispatch" in data["on"]
    assert data["on"]["push"]["tags"] == ["v*"]
    assert "refs/tags/v" in data["jobs"]["build"]["if"]
    steps = data["jobs"]["github-release"]["steps"]
    assert any(
        step.get("name") == "Require reviewed release notes for this tag"
        and "docs/releases/${GITHUB_REF_NAME}.md" in step.get("run", "")
        for step in steps
    )
    publish = [
        step for step in steps if step.get("uses", "").startswith("softprops/action-gh-release@")
    ]
    assert len(publish) == 1
    assert publish[0]["with"]["body_path"] == "docs/releases/${{ github.ref_name }}.md"
    assert "generate_release_notes" not in publish[0]["with"]
    assert (ROOT / "docs/releases/v0.3.0.md").is_file()
