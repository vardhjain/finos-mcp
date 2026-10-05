"""The maintenance scripts' safety checks. No network: only pure helpers are called."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(relative: str, name: str) -> ModuleType:
    path = REPO / relative
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(path.parent))


def test_github_token_is_never_sent_to_maven_central(monkeypatch: pytest.MonkeyPatch) -> None:
    """The CDM sync downloads schema archives from Maven Central with the same helper it
    uses for GitHub, and used to attach the GitHub token to both."""
    cdm = _load("servers/cdm/scripts/sync_upstream.py", "cdm_sync_upstream")
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    maven = cdm._headers(f"{cdm.MAVEN_BASE}/7.5.0/cdm-json-schema-7.5.0.zip", accept_json=False)
    assert "Authorization" not in maven
    assert "Authorization" in cdm._headers("https://api.github.com/repos/finos/x")
    assert "Authorization" in cdm._headers("https://raw.githubusercontent.com/finos/x/y")
    assert "Authorization" not in cdm._headers("https://api.github.com.evil.example/x")


def test_crlf_is_normalised_before_hashing() -> None:
    cdm = _load("servers/cdm/scripts/sync_upstream.py", "cdm_sync_upstream")
    assert cdm._lf(b'{\r\n  "a": 1\r\n}\r\n') == b'{\n  "a": 1\n}\n'


def test_rosetta_extraction_fails_loudly_when_it_drops_a_declaration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A declaration in a shape the extraction regexes do not expect must stop the sync,
    not vanish from root_types.json."""
    cdm = _load("servers/cdm/scripts/sync_upstream.py", "cdm_sync_upstream")
    monkeypatch.setattr(cdm, "VENDOR_DIR", tmp_path / "vendor")  # never touch the real tree
    (tmp_path / "vendor").mkdir()
    sources = tmp_path / "rosetta"
    sources.mkdir()
    (sources / "event-qualification-func.rosetta").write_text(
        "namespace cdm.event\n", encoding="utf-8"
    )
    multi_line_doc = (
        "namespace cdm.x\n\n"
        'type A: <"doc that spans\n two lines">\n'
        "    [rootType]\n"
        "    a string (1..1)\n"
    )
    (sources / "types.rosetta").write_text(multi_line_doc, encoding="utf-8")
    with pytest.raises(SystemExit, match="extraction is incomplete"):
        cdm.run_extraction(sources)
    assert not list((tmp_path / "vendor").iterdir())


def test_an_unresolvable_context_link_stops_intent_generation() -> None:
    gen = _load("servers/fdc3/scripts/generate_intents.py", "fdc3_generate_intents")
    section = (
        "\n- [Instrument](../../context/ref/Instrument)\n- [Mystery](../../context/ref/Mystery)\n"
    )
    with pytest.raises(SystemExit, match="Mystery"):
        gen._parse_possible_contexts(section, _table_with_instrument(gen))


def _table_with_instrument(gen: ModuleType) -> dict[str, str]:
    """The generator's own lookup table, built from the vendored schemas."""
    schemas = REPO / "servers/fdc3/src/finos_mcp/fdc3/_vendor/schemas/context"
    table, _entries = gen._load_context_index(schemas)
    return dict(table)
