"""Read-only verification of three published official MCP Registry entries.

Usage: python scripts/check_registry_discoverability.py
Fetches public, unauthenticated MCP Registry v0.1 API endpoints. Does not
authenticate, mutate or publish anything.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ("aigf", "cdm", "fdc3")
REGISTRY = "https://registry.modelcontextprotocol.io/v0.1"


def verify_entry(component: str) -> None:
    """Require the exact released metadata from the public Registry API."""
    manifest = json.loads((ROOT / "registry" / component / "server.json").read_text())
    name = manifest["name"]
    version = manifest["version"]
    url = f"{REGISTRY}/servers/{quote(name, safe='')}/versions/{quote(version, safe='')}"
    with urlopen(url, timeout=20) as response:
        payload = json.load(response)
    server = payload["server"]
    expected_package = manifest["packages"][0]
    assert server["name"] == name, f"{component}: unexpected public Registry name"
    assert server["version"] == version, f"{component}: unexpected public Registry version"
    assert server["repository"]["url"] == "https://github.com/vardhjain/finos-mcp"
    assert any(
        package.get("registryType") == "pypi"
        and package.get("identifier") == expected_package["identifier"]
        and package.get("version") == expected_package["version"]
        and package.get("transport", {}).get("type") == "stdio"
        for package in server.get("packages", [])
    ), f"{component}: expected public PyPI/stdio package missing"
    metadata = payload.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
    assert metadata.get("status", "active") == "active", (
        f"{component}: Registry listing is not active"
    )
    print(f"PASS: {name}=={version}: public Registry API returned matching active stdio package")
    print(f"API: {url}")


def main() -> int:
    failed = False
    for component in COMPONENTS:
        try:
            verify_entry(component)
        except (
            HTTPError,
            URLError,
            TimeoutError,
            KeyError,
            ValueError,
            TypeError,
            AssertionError,
        ) as exc:
            print(f"UNVERIFIED: {component}: {exc}", file=sys.stderr)
            failed = True
    if failed:
        print("At least one public listing could not be verified.", file=sys.stderr)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
