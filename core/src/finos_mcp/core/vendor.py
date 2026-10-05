"""Provenance for vendored upstream content.

Every ``_vendor/`` directory carries a ``SOURCE.json`` describing where its files
came from and a sha256 for each.  ``verify()`` runs at server start and in tests;
a mismatch fails fast so a server never serves content it cannot attribute.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
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


# --------------------------------------------------------------- sync-script helpers

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def fetch(
    request: urllib.request.Request,
    *,
    timeout: float = 60,
    attempts: int = 4,
    sleep: Callable[[float], None] = time.sleep,
) -> bytes:
    """Read one URL for a sync script, retrying what is worth retrying.

    A timeout, a dropped connection or a 429/5xx is retried with a growing pause. Any other
    HTTP error is raised at once as `urllib.error.HTTPError`, for the caller to report. When
    the retries run out on a network error, the script stops with a one-line message
    instead of a traceback.
    """
    for attempt in range(attempts):
        last = attempt == attempts - 1
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data: bytes = response.read()
                return data
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRYABLE_STATUS or last:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if last:
                raise SystemExit(f"Network error for {request.full_url}: {exc}") from exc
        sleep(2.0**attempt)
    raise AssertionError("unreachable")  # pragma: no cover


@contextmanager
def restore_on_failure(vendor_dir: Path) -> Iterator[None]:
    """Run a sync that rewrites `vendor_dir` in place; put the old tree back if it fails.

    The sync scripts clear what they manage and then download its replacement. Without
    this, a failure part-way (a network error, a missing tag, an extraction check) leaves
    a half-written tree whose manifest no longer verifies, and the server refuses to start
    until the directory is restored from git.
    """
    backup: Path | None = None
    if vendor_dir.exists():
        backup = Path(tempfile.mkdtemp(prefix="finos-vendor-backup-")) / vendor_dir.name
        shutil.copytree(vendor_dir, backup)
    try:
        yield
    except BaseException:
        if backup is not None:
            shutil.rmtree(vendor_dir, ignore_errors=True)
            shutil.copytree(backup, vendor_dir)
            print(f"Sync failed; restored {vendor_dir} to its previous state.")
        raise
    finally:
        if backup is not None:
            shutil.rmtree(backup.parent, ignore_errors=True)
