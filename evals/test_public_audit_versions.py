"""Public audits must be able to verify the released version during preparation."""

import io
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_pypi_audit_uses_explicit_published_version() -> None:
    audit = runpy.run_path(str(ROOT / "scripts/check_pypi_mcp_ownership.py"))["audit"]
    urls = []

    def fetch(url: str, timeout: int) -> io.BytesIO:
        urls.append(url)
        component = url.split("finos-mcp-")[1].split("/")[0]
        payload = {
            "info": {"description": f"<!-- mcp-name: io.github.vardhjain/finos-mcp-{component} -->"}
        }
        return io.BytesIO(json.dumps(payload).encode())

    assert audit(fetch=fetch, version_override="0.3.2") == 0
    assert len(urls) == 3
    assert all(url.endswith("/0.3.2/json") for url in urls)


def test_registry_override_checks_both_record_and_package_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify = runpy.run_path(str(ROOT / "scripts/check_registry_discoverability.py"))["verify_entry"]
    server = json.loads((ROOT / "registry/aigf/server.json").read_text())
    server["version"] = "0.3.2"
    server["packages"][0]["version"] = "0.3.2"
    urls = []

    def fetch(url: str, timeout: int) -> io.BytesIO:
        urls.append(url)
        return io.BytesIO(json.dumps({"server": server}).encode())

    monkeypatch.setitem(verify.__globals__, "urlopen", fetch)
    verify("aigf", "0.3.2")
    assert urls[0].endswith("/versions/0.3.2")
    server["packages"][0]["version"] = "0.3.3"
    with pytest.raises(AssertionError, match="expected public PyPI/stdio package missing"):
        verify("aigf", "0.3.2")
