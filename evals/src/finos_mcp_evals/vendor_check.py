"""Verify every vendored directory against its SOURCE.json manifest.

Usage: ``uv run python -m finos_mcp_evals.vendor_check``
Exit status is non-zero if any present manifest fails verification.  A server
whose ``_vendor`` directory does not exist yet is reported and skipped.

Also rejects CRLF line endings in vendored files.  ``.gitattributes`` normalises
text to LF on commit, so a file written with Windows line endings hashes one way
on the machine that vendored it and another way everywhere else -- which shows up
as an opaque "changed" list in CI.  Catching it here names the real problem.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from finos_mcp.core import VendorIntegrityError, verify

SERVERS = ("aigf", "cdm", "fdc3")


def vendor_dir(server: str) -> Path | None:
    try:
        module = importlib.import_module(f"finos_mcp.{server}")
    except ImportError:
        return None
    base = Path(module.__file__ or "").parent / "_vendor"
    return base if base.is_dir() else None


def crlf_files(vendor: Path) -> list[str]:
    """Vendored files containing CRLF, which git would rewrite on checkout."""
    out: list[str] = []
    for path in sorted(vendor.rglob("*")):
        if not path.is_file() or path.name == "SOURCE.json":
            continue
        chunk = path.read_bytes()[:2_000_000]
        if b"\r\n" in chunk:
            out.append(path.relative_to(vendor).as_posix())
    return out


def main(argv: list[str] | None = None) -> int:
    failures = 0
    for server in SERVERS:
        path = vendor_dir(server)
        if path is None:
            sys.stdout.write(f"{server:5}  skipped (no _vendor directory)\n")
            continue
        crlf = crlf_files(path)
        if crlf:
            failures += 1
            sys.stdout.write(
                f"{server:5}  FAILED  CRLF line endings in vendored files (git normalises these "
                f"to LF on commit, so the recorded hashes cannot match a fresh clone): "
                f"{crlf[:5]}{' ...' if len(crlf) > 5 else ''}\n"
                f'         fix: re-run the sync script (its writers must pass newline="\\n"), '
                f"then rebuild SOURCE.json\n"
            )
            continue
        try:
            manifest = verify(path)
        except VendorIntegrityError as exc:
            failures += 1
            sys.stdout.write(f"{server:5}  FAILED  {exc}\n")
            continue
        sys.stdout.write(
            f"{server:5}  ok      {manifest.upstream_repo}@{manifest.ref} "
            f"({(manifest.commit_sha or manifest.version or '?')[:12]}) "
            f"{len(manifest.files)} files, {manifest.license}\n"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
