"""Provenance for vendored upstream content.

Every ``_vendor/`` directory carries a ``SOURCE.json`` describing where its files
came from and a sha256 for each.  ``verify()`` runs at server start and in tests;
a mismatch fails fast so a server never serves content it cannot attribute.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

MANIFEST_NAME = "SOURCE.json"


class VendorIntegrityError(RuntimeError):
    pass


class SourceManifest(BaseModel):
    upstream_repo: str
    ref: str
    commit_sha: str | None = None
    version: str | None = None
    fetched_at: str
    license: str
    license_url: str | None = None
    notes: str | None = None
    files: dict[str, str] = Field(default_factory=dict)  # relative posix path -> sha256

    @classmethod
    def load(cls, vendor_dir: Path) -> SourceManifest:
        path = vendor_dir / MANIFEST_NAME
        if not path.exists():
            raise VendorIntegrityError(f"missing {path}")
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, vendor_dir: Path) -> None:
        vendor_dir.mkdir(parents=True, exist_ok=True)
        (vendor_dir / MANIFEST_NAME).write_text(
            self.model_dump_json(indent=2, exclude_none=True) + "\n", encoding="utf-8", newline="\n"
        )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_tree(vendor_dir: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(vendor_dir.rglob("*")):
        if p.is_file() and p.name != MANIFEST_NAME and "__pycache__" not in p.parts:
            out[p.relative_to(vendor_dir).as_posix()] = sha256_file(p)
    return out


def build_manifest(
    vendor_dir: Path,
    *,
    upstream_repo: str,
    ref: str,
    license: str,
    commit_sha: str | None = None,
    version: str | None = None,
    license_url: str | None = None,
    notes: str | None = None,
) -> SourceManifest:
    return SourceManifest(
        upstream_repo=upstream_repo,
        ref=ref,
        commit_sha=commit_sha,
        version=version,
        fetched_at=datetime.now(UTC).isoformat(timespec="seconds"),
        license=license,
        license_url=license_url,
        notes=notes,
        files=hash_tree(vendor_dir),
    )


def verify(vendor_dir: Path) -> SourceManifest:
    """Check every manifest entry exists with the recorded hash and nothing is missing."""
    manifest = SourceManifest.load(vendor_dir)
    actual = hash_tree(vendor_dir)
    missing = sorted(set(manifest.files) - set(actual))
    extra = sorted(set(actual) - set(manifest.files))
    changed = sorted(k for k in manifest.files if k in actual and actual[k] != manifest.files[k])
    if missing or extra or changed:
        raise VendorIntegrityError(
            f"vendored content in {vendor_dir} does not match {MANIFEST_NAME}: "
            f"missing={missing[:5]} extra={extra[:5]} changed={changed[:5]}"
        )
    if not manifest.files:
        raise VendorIntegrityError(f"{vendor_dir} manifest lists no files")
    return manifest


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))
