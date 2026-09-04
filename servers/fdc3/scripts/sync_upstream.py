"""Vendor context schemas, intent reference docs and Intents.ts from finos/FDC3.

Stdlib only. Usage::

    uv run python servers/fdc3/scripts/sync_upstream.py --ref v2.2.3

Resolves ``--ref`` (a tag, branch, or SHA; default ``v2.2.3``, the latest release
per PLAN.md 1.3) to a commit SHA via the GitHub REST API, fetches the full
recursive git tree at that SHA, and *locates* (rather than assumes) the paths
of interest, because the FDC3 monorepo has moved these directories across
releases:

* the context schemas directory -- the directory containing both
  ``context.schema.json`` and ``instrument.schema.json`` (on ``main`` and at
  ``v2.2.3`` this is ``packages/fdc3-context/schemas/context``; older tags used
  ``src/context/schemas``). The repo tree also contains versioned *copies* of
  these schemas under ``website/static/schemas/<version>/context`` and
  ``website/versioned_docs/...`` for the docs site -- those are excluded so we
  vendor the authoritative source, not a served copy.
* the intent reference docs directory -- the directory containing both
  ``ViewChart.md`` and ``ViewInstrument.md``, excluding ``versioned_docs``.
* ``Intents.ts`` -- the shortest path ending in ``Intents.ts`` (the package
  source, not any built/dist copy).
* the license file -- ``LICENSE.md`` if present, else ``LICENSE``, at repo root.

Downloads each via raw.githubusercontent.com at the resolved SHA into
``servers/fdc3/src/finos_mcp/fdc3/_vendor/``, regenerates ``intents.json`` from
the freshly downloaded content (so its hash is covered by the provenance
manifest), then writes ``SOURCE.json`` via ``finos_mcp.core.build_manifest``.

No network access happens anywhere else in this repository at runtime: this
script is the only place finos-mcp-fdc3 ever talks to the internet, and it is
never imported or run by the server itself.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

UPSTREAM_REPO = "finos/FDC3"
API_BASE = f"https://api.github.com/repos/{UPSTREAM_REPO}"
RAW_BASE = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}"
LICENSE_URL = "https://github.com/finos/FDC3/blob/main/LICENSE.md"

VENDOR_DIR = Path(__file__).resolve().parents[1] / "src" / "finos_mcp" / "fdc3" / "_vendor"

_REQUIRED_SCHEMA_FILES = ("context.schema.json", "instrument.schema.json")
_REQUIRED_INTENT_DOCS = ("ViewChart.md", "ViewInstrument.md")
_EXCLUDE_DIR_MARKERS = ("website/", "node_modules/")


def _headers() -> dict[str, str]:
    headers = {
        "User-Agent": "finos-mcp-fdc3-sync-upstream",
        "Accept": "application/vnd.github+json",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitHub API request failed ({exc.code}) for {url}:\n{body}") from exc


def _get_text(url: str) -> str:
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Download failed ({exc.code}) for {url}") from exc


def resolve_sha(ref: str) -> str:
    data = _get_json(f"{API_BASE}/commits/{ref}")
    sha = data.get("sha")
    if not isinstance(sha, str) or not sha:
        raise SystemExit(f"Could not resolve ref {ref!r} to a commit SHA: {data!r}")
    return sha


def fetch_tree_paths(sha: str) -> set[str]:
    data = _get_json(f"{API_BASE}/git/trees/{sha}?recursive=1")
    if data.get("truncated"):
        raise SystemExit(
            f"Git tree at {sha} was truncated by the GitHub API; "
            "sync_upstream.py needs the non-recursive listing logic extended."
        )
    tree = data.get("tree")
    if not isinstance(tree, list):
        raise SystemExit(f"Unexpected git tree response for {sha}: {data!r}")
    return {entry["path"] for entry in tree if entry.get("type") == "blob"}


def find_schemas_dir(paths: set[str]) -> str:
    """Locate the directory holding the canonical (non-website-copy) context schemas."""
    context_dirs = {p.rsplit("/", 1)[0] for p in paths if p.endswith("/context.schema.json")}
    candidates = [
        d
        for d in context_dirs
        if f"{d}/instrument.schema.json" in paths
        and not any(marker in f"{d}/" for marker in _EXCLUDE_DIR_MARKERS)
    ]
    if not candidates:
        # Relax the website exclusion rather than fail outright.
        candidates = [d for d in context_dirs if f"{d}/instrument.schema.json" in paths]
    if not candidates:
        raise SystemExit(
            f"Could not locate a directory containing {_REQUIRED_SCHEMA_FILES} in the tree"
        )
    candidates.sort(key=len)
    return candidates[0]


def find_intents_dir(paths: set[str]) -> str:
    """Locate the directory holding the current (non-versioned-docs) intent ref pages."""
    view_chart_dirs = {p.rsplit("/", 1)[0] for p in paths if p.endswith("/ViewChart.md")}
    candidates = [
        d
        for d in view_chart_dirs
        if f"{d}/ViewInstrument.md" in paths and "versioned_docs" not in d
    ]
    if not candidates:
        candidates = [d for d in view_chart_dirs if f"{d}/ViewInstrument.md" in paths]
    if not candidates:
        raise SystemExit(
            f"Could not locate a directory containing {_REQUIRED_INTENT_DOCS} in the tree"
        )
    candidates.sort(key=len)
    return candidates[0]


def find_intents_ts(paths: set[str]) -> str:
    candidates = sorted(p for p in paths if p == "Intents.ts" or p.endswith("/Intents.ts"))
    if not candidates:
        raise SystemExit("Could not locate Intents.ts in the tree")
    candidates.sort(key=len)
    return candidates[0]


def find_license(paths: set[str]) -> str:
    for candidate in ("LICENSE.md", "LICENSE"):
        if candidate in paths:
            return candidate
    raise SystemExit("Could not locate LICENSE.md or LICENSE at repo root")


def list_dir_files(paths: set[str], dir_path: str, suffix: str) -> list[str]:
    prefix = f"{dir_path}/"
    return sorted(
        p[len(prefix) :]
        for p in paths
        if p.startswith(prefix) and p.endswith(suffix) and "/" not in p[len(prefix) :]
    )


def download_file(upstream_path: str, sha: str, dest: Path) -> None:
    text = _get_text(f"{RAW_BASE}/{sha}/{upstream_path}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")


def clear_stale(vendor_dir: Path) -> None:
    """Remove everything we manage so a sync never leaves behind deleted upstream files."""
    schemas_dir = vendor_dir / "schemas"
    if schemas_dir.exists():
        shutil.rmtree(schemas_dir)
    intents_dir = vendor_dir / "intents"
    if intents_dir.exists():
        shutil.rmtree(intents_dir)
    for extra in ("Intents.ts", "LICENSE.md", "intents.json"):
        path = vendor_dir / extra
        if path.exists():
            path.unlink()


def _version_from_ref(ref: str) -> str:
    return ref[1:] if re.match(r"^v\d", ref) else ref


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ref", default="v2.2.3", help="Tag, branch, or SHA to sync (default: v2.2.3)"
    )
    args = parser.parse_args(argv)

    sha = resolve_sha(args.ref)
    print(f"Resolved ref {args.ref!r} -> {sha}")

    paths = fetch_tree_paths(sha)
    print(f"Fetched recursive tree: {len(paths)} blob(s)")

    schemas_dir = find_schemas_dir(paths)
    intents_dir = find_intents_dir(paths)
    intents_ts_path = find_intents_ts(paths)
    license_path = find_license(paths)
    print(f"Context schemas directory: {schemas_dir}")
    print(f"Intent reference docs directory: {intents_dir}")
    print(f"Intents.ts: {intents_ts_path}")
    print(f"License file: {license_path}")

    schema_files = list_dir_files(paths, schemas_dir, ".schema.json")
    intent_docs = list_dir_files(paths, intents_dir, ".md")
    if not schema_files:
        raise SystemExit(f"No *.schema.json files found under {schemas_dir}")
    if not intent_docs:
        raise SystemExit(f"No *.md files found under {intents_dir}")

    clear_stale(VENDOR_DIR)

    print(f"{schemas_dir}: {len(schema_files)} schema file(s)")
    for name in schema_files:
        download_file(f"{schemas_dir}/{name}", sha, VENDOR_DIR / "schemas" / "context" / name)

    print(f"{intents_dir}: {len(intent_docs)} intent doc(s)")
    for name in intent_docs:
        download_file(f"{intents_dir}/{name}", sha, VENDOR_DIR / "intents" / name)

    print(f"{intents_ts_path} -> _vendor/Intents.ts")
    download_file(intents_ts_path, sha, VENDOR_DIR / "Intents.ts")

    print(f"{license_path} -> _vendor/LICENSE.md")
    download_file(license_path, sha, VENDOR_DIR / "LICENSE.md")

    # Regenerate intents.json from the freshly downloaded content BEFORE the
    # manifest is built, so its hash is included in SOURCE.json.
    from generate_intents import write_intents_json

    intents_data = write_intents_json(VENDOR_DIR)
    print(f"Wrote intents.json with {intents_data['count']} intent(s)")

    from finos_mcp.core import build_manifest

    manifest = build_manifest(
        VENDOR_DIR,
        upstream_repo=UPSTREAM_REPO,
        ref=args.ref,
        commit_sha=sha,
        version=_version_from_ref(args.ref),
        license="Community-Spec-1.0",
        license_url=LICENSE_URL,
        notes=(
            "Context schemas, intent reference docs and Intents.ts vendored from "
            "finos/FDC3; intents.json generated by scripts/generate_intents.py"
        ),
    )
    manifest.save(VENDOR_DIR)

    print(f"Wrote SOURCE.json with {len(manifest.files)} file hashes")
    print(
        f"Counts: schemas={len(schema_files)}, intents={len(intent_docs)}, "
        f"intents.json={intents_data['count']}"
    )
    print(f"Commit SHA: {sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
