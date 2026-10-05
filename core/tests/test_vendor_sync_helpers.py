"""The helpers the sync scripts use to survive a failed run. No network."""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from finos_mcp.core import vendor
from finos_mcp.core.vendor import fetch, restore_on_failure


def _tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_a_failed_sync_leaves_the_vendored_tree_as_it_was(tmp_path: Path) -> None:
    """The scripts clear what they manage before downloading its replacement. A failure
    part-way used to leave a half-written tree whose manifest no longer verified."""
    vendored = tmp_path / "_vendor"
    (vendored / "risks").mkdir(parents=True)
    (vendored / "risks" / "ri-1.md").write_text("risk one\n", encoding="utf-8")
    (vendored / "SOURCE.json").write_text("{}\n", encoding="utf-8")
    before = _tree(vendored)

    with pytest.raises(SystemExit), restore_on_failure(vendored):
        (vendored / "risks" / "ri-1.md").unlink()  # cleared
        (vendored / "risks" / "ri-2.md").write_text("half a download", encoding="utf-8")
        raise SystemExit("Download failed (503)")

    assert _tree(vendored) == before


def test_a_successful_sync_keeps_its_changes(tmp_path: Path) -> None:
    vendored = tmp_path / "_vendor"
    vendored.mkdir()
    (vendored / "old.md").write_text("old\n", encoding="utf-8")
    with restore_on_failure(vendored):
        (vendored / "old.md").unlink()
        (vendored / "new.md").write_text("new\n", encoding="utf-8")
    assert _tree(vendored) == {"new.md": "new\n"}


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test/x", code, "error", {}, None)  # type: ignore[arg-type]


def _scripted(monkeypatch: pytest.MonkeyPatch, outcomes: list[Any]) -> list[float]:
    """Make urlopen return or raise the given outcomes in turn; record the pauses."""
    remaining = list(outcomes)

    def urlopen(request: object, timeout: float) -> _Response:
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _Response(outcome)

    monkeypatch.setattr(vendor.urllib.request, "urlopen", urlopen)
    return []


REQUEST = urllib.request.Request("https://example.test/x")


def test_fetch_retries_transient_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    pauses = _scripted(monkeypatch, [_http_error(503), TimeoutError("slow"), b"payload"])
    assert fetch(REQUEST, sleep=pauses.append) == b"payload"
    assert pauses == [1.0, 2.0]


def test_fetch_does_not_retry_a_missing_file(monkeypatch: pytest.MonkeyPatch) -> None:
    pauses = _scripted(monkeypatch, [_http_error(404), b"never reached"])
    with pytest.raises(urllib.error.HTTPError):
        fetch(REQUEST, sleep=pauses.append)
    assert pauses == []


def test_fetch_gives_up_with_a_clear_message(monkeypatch: pytest.MonkeyPatch) -> None:
    pauses = _scripted(monkeypatch, [urllib.error.URLError("no route")] * 4)
    with pytest.raises(SystemExit, match="Network error for"):
        fetch(REQUEST, sleep=pauses.append)
    assert len(pauses) == 3
