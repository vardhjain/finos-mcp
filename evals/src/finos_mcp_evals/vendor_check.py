"""Verify every vendored directory against its SOURCE.json manifest.

Usage: ``uv run python -m finos_mcp_evals.vendor_check``
Exit status is non-zero if any present manifest fails verification.  A server
whose ``_vendor`` directory does not exist yet is reported and skipped.
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


def main(argv: list[str] | None = None) -> int:
    failures = 0
    for server in SERVERS:
        path = vendor_dir(server)
        if path is None:
            sys.stdout.write(f"{server:5}  skipped (no _vendor directory)\n")
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
