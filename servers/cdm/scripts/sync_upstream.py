"""Vendor CDM JSON Schema, curated samples, and rosetta-derived facts.

Stdlib only (urllib, zipfile, json, pathlib, argparse). Usage::

    uv run python servers/cdm/scripts/sync_upstream.py --version 7.2.0 --legacy-version 6.27.0

Three upstream sources feed ``servers/cdm/src/finos_mcp/cdm/_vendor/``:

1. The JSON Schema distribution is a zip on Maven Central
   (``org.finos.cdm:cdm-json-schema:<version>``), unrelated to GitHub releases
   (CDM ships no GitHub release assets). Every ``*.schema.json`` entry from the
   primary ``--version`` zip is unzipped flat into ``_vendor/schemas/``. The
   ``--legacy-version`` zip is *also* downloaded and unzipped, to
   ``_vendor/schemas-<legacy-version>/``, so that legacy-format samples (see
   point 2) can be validated against a JSON Schema of matching vintage instead
   of only the newer primary schema, which describes a different JSON shape
   (see PLAN.md 1.2 and ``CdmRegistry.schema_registry_for``).
2. A curated set of Rune-format (CDM 7.x) and legacy-format (CDM <=6) sample
   BusinessEvent outputs is pulled from two different tags of
   ``finos/common-domain-model`` on GitHub via the git trees API, because the
   two JSON *shapes* (``@type``/``@key``/... vs. ``{"value":..,"meta":..}``)
   only diverged at CDM 7 (see PLAN.md 1.2) and we want real positive samples
   of both for the dual validator this vendoring feeds.
3. Every ``.rosetta`` DSL source file at the ``--version`` tag is downloaded to
   a temp directory (never vendored -- it is not JSON, and only a handful of
   facts are extracted from it) and fed to ``extract_rosetta.py``, which is
   imported from this same ``scripts/`` directory. Only
   ``event-qualification-func.rosetta`` itself is additionally vendored
   verbatim, as citable primary source for the 35 ``Qualify_*`` functions.

No network access happens anywhere else in this repository at runtime: this
script is the only place finos-mcp-cdm ever talks to the internet, and it is
never imported or run by the server itself.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

UPSTREAM_REPO = "finos/common-domain-model"
API_BASE = f"https://api.github.com/repos/{UPSTREAM_REPO}"
RAW_BASE = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}"
MAVEN_BASE = "https://repo1.maven.org/maven2/org/finos/cdm/cdm-json-schema"

CDM_PKG_DIR = Path(__file__).resolve().parents[1] / "src" / "finos_mcp" / "cdm"
VENDOR_DIR = CDM_PKG_DIR / "_vendor"
SCHEMAS_DIR = VENDOR_DIR / "schemas"
SAMPLES_RUNE_DIR = VENDOR_DIR / "samples" / "rune"
SAMPLES_LEGACY_DIR = VENDOR_DIR / "samples" / "legacy"
ROSETTA_VENDOR_DIR = VENDOR_DIR / "rosetta"

# Expected cdm-json-schema-<version>.zip sizes (bytes), per PLAN.md 1.2 -- used
# only for a non-fatal sanity warning if Maven Central ever reshuffles a release.
EXPECTED_SCHEMA_ZIP_SIZES = {"7.2.0": 944_682, "6.27.0": 392_238}

LICENSE_URL = "https://github.com/finos/common-domain-model/blob/master/LICENSE.md"

RUNE_SAMPLE_BASE = "rosetta-source/src/main/resources/functions/business-event/"
LEGACY_SAMPLE_BASE = "rosetta-source/src/main/resources/cdm-sample-files/functions/business-event/"
ROSETTA_SOURCE_DIR = "rosetta-source/src/main/rosetta/"
EVENT_QUALIFICATION_FILE = "event-qualification-func.rosetta"

RUNE_SAMPLE_CAP_TOTAL = 40
RUNE_SAMPLE_CAP_PER_DIR = 4
LEGACY_SAMPLE_CAP_TOTAL = 12
LEGACY_SAMPLE_CAP_PER_DIR = 3


def _headers(*, accept_json: bool = True) -> dict[str, str]:
    headers = {"User-Agent": "finos-mcp-cdm-sync-upstream"}
    if accept_json:
        headers["Accept"] = "application/vnd.github+json"
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"GitHub API request failed ({exc.code}) for {url}:\n{body}") from exc


def _get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers=_headers(accept_json=False))
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Download failed ({exc.code}) for {url}") from exc


def resolve_sha(ref: str) -> str:
    data = _get_json(f"{API_BASE}/commits/{ref}")
    sha = data.get("sha")
    if not isinstance(sha, str) or not sha:
        raise SystemExit(f"Could not resolve ref {ref!r} to a commit SHA: {data!r}")
    return sha


def list_tree(sha: str) -> list[dict[str, Any]]:
    data = _get_json(f"{API_BASE}/git/trees/{sha}?recursive=1")
    if data.get("truncated"):
        raise SystemExit(
            f"Tree listing for {sha} was truncated by the GitHub API; "
            "narrow the query or fetch subtrees individually."
        )
    tree = data.get("tree")
    if not isinstance(tree, list):
        raise SystemExit(f"Unexpected tree response for {sha}: {data!r}")
    return tree


def _clear(dir_path: Path) -> None:
    if dir_path.exists():
        shutil.rmtree(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)


# --- 1. JSON Schema zip from Maven Central ---------------------------------


def schemas_dir_for(version: str) -> Path:
    """Vendor directory for a given CDM JSON Schema version: the primary
    (7.2.0) set lives at ``_vendor/schemas/`` for backwards compatibility;
    every other vendored vintage lives at ``_vendor/schemas-<version>/``."""
    if version == "7.2.0":
        return SCHEMAS_DIR
    return VENDOR_DIR / f"schemas-{version}"


def _extract_schema_members(data: bytes) -> dict[str, bytes]:
    """Return ``{basename: content}`` for every ``*.schema.json`` member of
    ``data``, which is normally a genuine zip (as for 7.2.0) -- but, it turns
    out, ``cdm-json-schema-6.27.0.zip`` is actually a gzip-compressed tar
    archive despite its ``.zip`` extension and the ``application/zip``
    content-type Maven Central serves it with (confirmed via magic bytes and
    ``file(1)``; genuine upstream packaging quirk from that older release, not
    a download artifact). Dispatched on the leading gzip magic bytes rather
    than assumed from the version string, so a correctly-zipped artifact at
    any version is still handled the normal way."""
    if data[:2] == b"\x1f\x8b":
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            members = [m for m in tf.getmembers() if m.name.endswith(".schema.json")]
            print(
                f"Archive is gzip-compressed tar (not a real zip) with {len(tf.getnames())} "
                f"entries; {len(members)} are *.schema.json"
            )
            out: dict[str, bytes] = {}
            for member in members:
                fh = tf.extractfile(member)
                if fh is not None:
                    out[Path(member.name).name] = fh.read()
            return out

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        dirs = sorted({n.rsplit("/", 1)[0] + "/" for n in names if "/" in n})
        print(f"Zip contains {len(names)} entries; internal directories: {dirs}")
        schema_names = [n for n in names if n.endswith(".schema.json")]
        return {Path(name).name: zf.read(name) for name in schema_names}


def sync_schemas(version: str) -> int:
    dest_dir = schemas_dir_for(version)
    url = f"{MAVEN_BASE}/{version}/cdm-json-schema-{version}.zip"
    print(f"Downloading {url}")
    data = _get_bytes(url)
    expected_size = EXPECTED_SCHEMA_ZIP_SIZES.get(version)
    if expected_size is not None and len(data) != expected_size:
        print(
            f"WARNING: cdm-json-schema-{version}.zip is {len(data)} bytes, "
            f"expected {expected_size} bytes (per PLAN.md 1.2). Continuing anyway."
        )

    members = _extract_schema_members(data)
    if not members:
        raise SystemExit(f"No *.schema.json members found in cdm-json-schema-{version}.zip")

    _clear(dest_dir)
    for name, content in members.items():
        (dest_dir / name).write_bytes(content)
    print(f"Extracted {len(members)} *.schema.json files -> {dest_dir}")
    return len(members)


# --- 2. Curated samples from two GitHub tags --------------------------------


def _pick_func_outputs(
    tree: list[dict[str, Any]], base: str, *, cap_total: int, cap_per_dir: int
) -> list[str]:
    """Pick ``*-func-output.json`` paths under ``base``, grouped by immediate
    subdirectory, at most ``cap_per_dir`` per subdirectory and ``cap_total``
    overall. Deterministic: subdirectories and filenames are both sorted."""
    by_dir: dict[str, list[str]] = defaultdict(list)
    for entry in tree:
        path = entry.get("path", "")
        if entry.get("type") != "blob" or not path.startswith(base):
            continue
        if not path.endswith("-func-output.json"):
            continue
        rel = path[len(base) :]
        if "/" not in rel:
            continue  # not under an immediate subdirectory
        subdir = rel.split("/", 1)[0]
        by_dir[subdir].append(path)

    picked: list[str] = []
    for subdir in sorted(by_dir):
        if len(picked) >= cap_total:
            break
        remaining = cap_total - len(picked)
        take = min(cap_per_dir, remaining)
        picked.extend(sorted(by_dir[subdir])[:take])
    return picked


def sync_samples(
    *,
    rune_sha: str,
    rune_tree: list[dict[str, Any]],
    legacy_sha: str,
    legacy_tree: list[dict[str, Any]],
) -> tuple[int, int, list[str], list[str]]:
    _clear(SAMPLES_RUNE_DIR)
    _clear(SAMPLES_LEGACY_DIR)

    rune_paths = _pick_func_outputs(
        rune_tree,
        RUNE_SAMPLE_BASE,
        cap_total=RUNE_SAMPLE_CAP_TOTAL,
        cap_per_dir=RUNE_SAMPLE_CAP_PER_DIR,
    )
    if not rune_paths:
        raise SystemExit(
            f"No *-func-output.json samples found under {RUNE_SAMPLE_BASE} at {rune_sha}"
        )
    rune_subdirs = sorted({p[len(RUNE_SAMPLE_BASE) :].split("/", 1)[0] for p in rune_paths})
    for path in rune_paths:
        rel = path[len(RUNE_SAMPLE_BASE) :]
        subdir, filename = rel.split("/", 1)
        dest = SAMPLES_RUNE_DIR / f"{subdir}__{filename}"
        dest.write_bytes(_get_bytes(f"{RAW_BASE}/{rune_sha}/{path}"))
    print(
        f"Rune samples (7.2.0): {len(rune_paths)} file(s) from {len(rune_subdirs)} "
        f"subdirector(y/ies): {rune_subdirs}"
    )

    legacy_paths = _pick_func_outputs(
        legacy_tree,
        LEGACY_SAMPLE_BASE,
        cap_total=LEGACY_SAMPLE_CAP_TOTAL,
        cap_per_dir=LEGACY_SAMPLE_CAP_PER_DIR,
    )
    if not legacy_paths:
        raise SystemExit(
            f"No *-func-output.json samples found under {LEGACY_SAMPLE_BASE} at {legacy_sha}; "
            "check the tree listing for the correct path at this tag."
        )
    legacy_subdirs = sorted({p[len(LEGACY_SAMPLE_BASE) :].split("/", 1)[0] for p in legacy_paths})
    for path in legacy_paths:
        rel = path[len(LEGACY_SAMPLE_BASE) :]
        subdir, filename = rel.split("/", 1)
        dest = SAMPLES_LEGACY_DIR / f"{subdir}__{filename}"
        dest.write_bytes(_get_bytes(f"{RAW_BASE}/{legacy_sha}/{path}"))
    print(
        f"Legacy samples (6.27.0): {len(legacy_paths)} file(s) from {len(legacy_subdirs)} "
        f"subdirector(y/ies): {legacy_subdirs}"
    )

    return len(rune_paths), len(legacy_paths), rune_subdirs, legacy_subdirs


# --- 3. .rosetta sources (temp dir) + extraction ----------------------------


def sync_rosetta(sha: str, tree: list[dict[str, Any]]) -> Path:
    rosetta_paths = sorted(
        entry["path"]
        for entry in tree
        if entry.get("type") == "blob"
        and entry["path"].startswith(ROSETTA_SOURCE_DIR)
        and entry["path"].endswith(".rosetta")
    )
    if not rosetta_paths:
        raise SystemExit(f"No .rosetta files found under {ROSETTA_SOURCE_DIR} at {sha}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="finos-cdm-rosetta-"))
    for path in rosetta_paths:
        text = _get_bytes(f"{RAW_BASE}/{sha}/{path}").decode("utf-8")
        (tmp_dir / Path(path).name).write_text(text, encoding="utf-8")
    print(f".rosetta sources: {len(rosetta_paths)} file(s) downloaded to {tmp_dir} (not vendored)")

    if EVENT_QUALIFICATION_FILE not in {p.name for p in tmp_dir.glob("*.rosetta")}:
        raise SystemExit(
            f"{EVENT_QUALIFICATION_FILE} was not found among downloaded .rosetta files"
        )

    _clear(ROSETTA_VENDOR_DIR)
    shutil.copyfile(
        tmp_dir / EVENT_QUALIFICATION_FILE, ROSETTA_VENDOR_DIR / EVENT_QUALIFICATION_FILE
    )
    print(f"Vendored {EVENT_QUALIFICATION_FILE} -> {ROSETTA_VENDOR_DIR}")

    return tmp_dir


def run_extraction(rosetta_dir: Path) -> tuple[int, int, int]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from extract_rosetta import extract_choice_types, extract_qualify, extract_root_types

    qualify = extract_qualify(rosetta_dir)
    root_types = extract_root_types(rosetta_dir)
    choices = extract_choice_types(rosetta_dir)

    (VENDOR_DIR / "qualify.json").write_text(
        json.dumps({"functions": qualify, "count": len(qualify)}, indent=2) + "\n", encoding="utf-8"
    )
    (VENDOR_DIR / "root_types.json").write_text(
        json.dumps({"root_types": root_types, "count": len(root_types)}, indent=2) + "\n",
        encoding="utf-8",
    )
    (VENDOR_DIR / "choice_types.json").write_text(
        json.dumps({"choice_types": choices, "count": len(choices)}, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"qualify.json: {len(qualify)} function(s) (expected 35)")
    print(
        f"root_types.json: {len(root_types)} type(s) (expected 16): {[r['name'] for r in root_types]}"
    )
    print(f"choice_types.json: {len(choices)} type(s): {[c['name'] for c in choices]}")
    return len(qualify), len(root_types), len(choices)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", required=True, help="CDM version to vendor, e.g. 7.2.0 (Rune JSON)"
    )
    parser.add_argument(
        "--legacy-version",
        required=True,
        help="Older CDM tag to source legacy-format JSON samples from, e.g. 6.27.0",
    )
    args = parser.parse_args(argv)

    VENDOR_DIR.mkdir(parents=True, exist_ok=True)

    schema_count = sync_schemas(args.version)
    legacy_schema_count = sync_schemas(args.legacy_version)

    rune_sha = resolve_sha(args.version)
    print(f"Resolved --version {args.version!r} -> {rune_sha}")
    legacy_sha = resolve_sha(args.legacy_version)
    print(f"Resolved --legacy-version {args.legacy_version!r} -> {legacy_sha}")

    rune_tree = list_tree(rune_sha)
    legacy_tree = list_tree(legacy_sha)

    rune_count, legacy_count, rune_subdirs, legacy_subdirs = sync_samples(
        rune_sha=rune_sha, rune_tree=rune_tree, legacy_sha=legacy_sha, legacy_tree=legacy_tree
    )

    tmp_rosetta_dir = sync_rosetta(rune_sha, rune_tree)
    try:
        qualify_count, root_type_count, choice_count = run_extraction(tmp_rosetta_dir)
    finally:
        shutil.rmtree(tmp_rosetta_dir, ignore_errors=True)

    from finos_mcp.core import build_manifest

    manifest = build_manifest(
        VENDOR_DIR,
        upstream_repo=UPSTREAM_REPO,
        ref=args.version,
        commit_sha=rune_sha,
        version=args.version,
        license="Community-Spec-1.0",
        license_url=LICENSE_URL,
        notes=(
            f"cdm-json-schema-{args.version}.zip from Maven Central, extracted to _vendor/schemas/ "
            f"(primary version={args.version}); cdm-json-schema-{args.legacy_version}.zip also "
            f"vendored to _vendor/schemas-{args.legacy_version}/ so legacy-format samples can be "
            "validated against a schema of matching vintage; samples from tags "
            f"{args.version} (Rune JSON) and {args.legacy_version} (legacy JSON); qualify.json and "
            "root_types.json extracted from .rosetta sources"
        ),
    )
    manifest.save(VENDOR_DIR)

    print(f"Wrote SOURCE.json with {len(manifest.files)} file hashes")
    print(
        "Summary: "
        f"schemas={schema_count}, legacy_schemas_{args.legacy_version}={legacy_schema_count}, "
        f"rune_samples={rune_count} ({rune_subdirs}), "
        f"legacy_samples={legacy_count} ({legacy_subdirs}), "
        f"qualify_functions={qualify_count}, root_types={root_type_count}, choice_types={choice_count}"
    )
    print(f"Commit SHA (7.2.0): {rune_sha}; Commit SHA (6.27.0): {legacy_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
