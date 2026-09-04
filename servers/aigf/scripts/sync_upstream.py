"""Vendor risks, mitigations and reference datasets from finos/ai-governance-framework.

Stdlib only. Usage::

    uv run python servers/aigf/scripts/sync_upstream.py [--ref main]

Resolves ``--ref`` (a branch, tag, or SHA; default ``main``) to a commit SHA via the
GitHub REST API, lists the three upstream directories we vendor at that SHA, downloads
each file via raw.githubusercontent.com, and writes them into
``servers/aigf/src/finos_mcp/aigf/_vendor/`` alongside a ``SOURCE.json`` provenance
manifest built with ``finos_mcp.core.build_manifest``.

No network access happens anywhere else in this repository at runtime: this script is
the only place finos-mcp ever talks to the internet, and it is never imported or run by
the servers themselves.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

UPSTREAM_REPO = "finos/ai-governance-framework"
API_BASE = f"https://api.github.com/repos/{UPSTREAM_REPO}"
RAW_BASE = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}"

VENDOR_DIR = Path(__file__).resolve().parents[1] / "src" / "finos_mcp" / "aigf" / "_vendor"

# (upstream directory, vendored subdirectory name, allowed file extensions)
VENDORED_DIRS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("docs/_risks", "risks", (".md",)),
    ("docs/_mitigations", "mitigations", (".md",)),
    ("docs/_data/references", "references", (".yml", ".yaml")),
)

LICENSE_URL = "https://github.com/finos/ai-governance-framework/blob/main/LICENSE"


def _headers() -> dict[str, str]:
    headers = {
        "User-Agent": "finos-mcp-aigf-sync-upstream",
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - trusted GitHub API
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitHub API request failed ({exc.code}) for {url}:\n{body}") from exc


def _get_text(url: str) -> str:
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - trusted raw content host
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Download failed ({exc.code}) for {url}") from exc


def resolve_sha(ref: str) -> str:
    data = _get_json(f"{API_BASE}/commits/{ref}")
    sha = data.get("sha")
    if not isinstance(sha, str) or not sha:
        raise SystemExit(f"Could not resolve ref {ref!r} to a commit SHA: {data!r}")
    return sha


def list_files(dir_path: str, sha: str, extensions: tuple[str, ...]) -> list[str]:
    data = _get_json(f"{API_BASE}/contents/{dir_path}?ref={sha}")
    if not isinstance(data, list):
        raise SystemExit(f"Unexpected contents API response for {dir_path}: {data!r}")
    names = [
        entry["name"]
        for entry in data
        if entry.get("type") == "file" and Path(entry["name"]).suffix.lower() in extensions
    ]
    return sorted(names)


def download_file(upstream_path: str, sha: str, dest: Path) -> None:
    text = _get_text(f"{RAW_BASE}/{sha}/{upstream_path}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")


def clear_stale(vendor_dir: Path) -> None:
    """Remove everything we manage so a sync never leaves behind deleted upstream files."""
    for _upstream_dir, subdir, _exts in VENDORED_DIRS:
        target = vendor_dir / subdir
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
    for extra in ("_config.yml", "LICENSE"):
        path = vendor_dir / extra
        if path.exists():
            path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="main", help="Branch, tag, or SHA to sync (default: main)")
    args = parser.parse_args(argv)

    sha = resolve_sha(args.ref)
    print(f"Resolved ref {args.ref!r} -> {sha}")
    clear_stale(VENDOR_DIR)

    counts: dict[str, int] = {}
    for upstream_dir, subdir, extensions in VENDORED_DIRS:
        names = list_files(upstream_dir, sha, extensions)
        print(f"{upstream_dir}: {len(names)} file(s)")
        for name in names:
            download_file(f"{upstream_dir}/{name}", sha, VENDOR_DIR / subdir / name)
        counts[subdir] = len(names)

    print("docs/_config.yml -> _vendor/_config.yml")
    download_file("docs/_config.yml", sha, VENDOR_DIR / "_config.yml")
    print("LICENSE -> _vendor/LICENSE")
    download_file("LICENSE", sha, VENDOR_DIR / "LICENSE")

    from finos_mcp.core import build_manifest

    manifest = build_manifest(
        VENDOR_DIR,
        upstream_repo=UPSTREAM_REPO,
        ref=args.ref,
        commit_sha=sha,
        license="CC-BY-4.0",
        license_url=LICENSE_URL,
        notes="Vendored risks, mitigations and reference datasets from the FINOS AI Governance Framework",
    )
    manifest.save(VENDOR_DIR)

    print(f"Wrote SOURCE.json with {len(manifest.files)} file hashes")
    print(
        "Counts: "
        + ", ".join(f"{subdir}={counts[subdir]}" for _upstream_dir, subdir, _exts in VENDORED_DIRS)
    )
    print(f"Commit SHA: {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
