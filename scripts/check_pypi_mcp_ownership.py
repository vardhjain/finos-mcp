"""Read-only audit of public PyPI ownership markers for MCP Registry drafts.

Usage: python scripts/check_pypi_mcp_ownership.py
No package upload, registry authentication, or publishing takes place.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ("aigf", "cdm", "fdc3")


def ownership_marker_present(description: str, registry_name: str) -> bool:
    """Match the Registry's mcp-name token with an explicit trailing boundary."""
    import re

    return (
        re.search(
            r"mcp-name:\s*" + re.escape(registry_name) + r"(?=\s|<|$)",
            description,
        )
        is not None
    )


def audit(fetch=urlopen) -> int:
    failed = False
    for component in COMPONENTS:
        draft = json.loads((ROOT / "registry" / component / "server.json").read_text())
        package = draft["packages"][0]
        name, version = package["identifier"], package["version"]
        url = f"https://pypi.org/pypi/{name}/{version}/json"
        try:
            with fetch(url, timeout=15) as response:
                info = json.load(response)["info"]
            description = info.get("description") or ""
            ok = ownership_marker_present(description, draft["name"])
            print(
                f"{'PASS' if ok else 'BLOCKED'}: {name}=={version}: "
                f"public PyPI ownership marker {'found' if ok else 'missing'}"
            )
            failed |= not ok
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError) as exc:
            print(f"UNVERIFIED: {name}=={version}: {exc}", file=sys.stderr)
            failed = True
    if failed:
        print("Registry publication remains blocked; no publishing attempted.", file=sys.stderr)
    else:
        print("All PyPI README markers found. Authentication and publisher checks remain separate.")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(audit())
