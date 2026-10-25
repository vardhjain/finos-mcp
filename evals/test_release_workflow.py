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


def test_container_publish_is_serialized_after_github_and_pypi_release() -> None:
    def load(name: str) -> dict[str, object]:
        value = yaml.load(
            (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"),
            Loader=yaml.BaseLoader,
        )
        assert isinstance(value, dict)
        return value

    gate = load("publish-release.yml")
    gate_script = gate["jobs"]["release-gate"]["steps"][-1]["run"]
    assert 'gh workflow run release.yml --ref "$TAG"' in gate_script
    assert "gh workflow run docker.yml" not in gate_script

    release = load("release.yml")
    jobs = release["jobs"]
    assert jobs["github-release"]["needs"] == ["build", "publish-pypi"]
    dispatch = jobs["dispatch-docker"]
    assert dispatch["needs"] == "github-release"
    assert "needs.github-release.result == 'success'" in dispatch["if"]
    assert dispatch["permissions"]["actions"] == "write"
    script = dispatch["steps"][0]["run"]
    # Dispatch runs without checkout, so the repository must be passed explicitly.
    assert (
        'gh workflow run docker.yml --repo "$GITHUB_REPOSITORY" '
        '--ref "$GITHUB_REF_NAME" -f push=true'
    ) in script
    assert 'GITHUB_REF_TYPE" != "tag' in script

    docker = load("docker.yml")
    assert "push" not in docker["on"]
    assert "workflow_dispatch" in docker["on"]
    steps = docker["jobs"]["build-and-smoke-test"]["steps"]
    pushes = [
        step
        for step in steps
        if step.get("name")
        in {"Log in to ghcr.io", "Build and push multi-arch with SBOM and provenance"}
    ]
    assert len(pushes) == 2
    for step in pushes:
        assert step["if"] == "inputs.push && startsWith(github.ref, 'refs/tags/v')"
