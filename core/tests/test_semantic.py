"""Tests for the optional dense `SemanticIndex` and `Catalog`'s hybrid search.

(a) below always runs, with or without the `semantic` extra installed: it pins down
that `mode="lexical"` is byte-for-byte the pre-hybrid algorithm and that a catalog
always builds (never raises) regardless of what `model2vec` does.

(b) is skipped via `pytest.importorskip` when `model2vec` is not installed -- CI and
local dev without the extra still get (a) and (c).

(c) always runs: a bad `FINOS_MCP_EMBEDDING_MODEL` must never break catalog
construction, whether or not `model2vec` itself is installed.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from finos_mcp.core import Catalog, Document, split_sections

DOCS = [
    Document(
        id="AIR-SEC-010",
        title="Prompt Injection",
        aliases=["ri-10", "10"],
        body="Adversarial instructions embedded in inputs cause the model to deviate from its task.",
        sections=split_sections(
            "## Summary\nAttackers hide instructions in documents.\n## Impact\nData exfiltration."
        ),
    ),
    Document(
        id="AIR-PREV-020",
        title="MCP Server Security Governance",
        aliases=["mi-20", "20"],
        body="Govern MCP servers: vetting, allow-listing, monitoring of tool servers used by agents.",
        sections=split_sections(
            "## Purpose\nControl which MCP servers an agent may call.\n## Guidance\nUse allow lists."
        ),
    ),
    Document(
        id="AIR-PREV-004",
        title="Prompt Injection Filtering",
        aliases=["mi-4", "4"],
        body="Filter and detect prompt injection attempts before they reach the model.",
    ),
]


def make_catalog() -> Catalog:
    return Catalog(DOCS, kind="record", citation_uri=lambda d: f"test://{d.id}")


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("FINOS_MCP_SEARCH_MODE", raising=False)
    monkeypatch.delenv("FINOS_MCP_EMBEDDING_MODEL", raising=False)
    yield


# ------------------------------------------------------------------ (a) lexical


def test_lexical_mode_matches_pre_hybrid_algorithm(clean_env: None) -> None:
    cat = make_catalog()
    hits = cat.search("allow list MCP servers agents call", k=3, mode="lexical")
    assert hits and hits[0].id == "AIR-PREV-020"
    assert hits[0].citation_uri == "test://AIR-PREV-020"
    assert hits[0].snippet

    assert cat.search("", k=3, mode="lexical") == []

    only_prev = cat.search(
        "prompt injection", k=5, mode="lexical", predicate=lambda d: d.id.startswith("AIR-PREV")
    )
    assert {h.id for h in only_prev} == {"AIR-PREV-004"}


def test_catalog_always_builds_and_exposes_status(clean_env: None) -> None:
    cat = make_catalog()
    assert isinstance(cat.semantic_status, str) and cat.semantic_status
    # semantic is either a working SemanticIndex or None -- never a half-built object.
    assert cat.semantic is None or cat.semantic.rank("prompt injection") is not None


def test_search_mode_env_override(clean_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINOS_MCP_SEARCH_MODE", "lexical")
    cat = make_catalog()
    forced = cat.search("prompt injection", k=5, predicate=lambda d: d.id.startswith("AIR-PREV"))
    explicit = cat.search(
        "prompt injection", k=5, mode="lexical", predicate=lambda d: d.id.startswith("AIR-PREV")
    )
    assert [h.id for h in forced] == [h.id for h in explicit] == ["AIR-PREV-004"]


# -------------------------------------------------------------------- (b) hybrid


def test_hybrid_mode_available_with_model2vec(clean_env: None) -> None:
    pytest.importorskip("model2vec")
    cat = make_catalog()
    assert cat.semantic is not None, cat.semantic_status
    assert cat.semantic_status.startswith("enabled:")

    lexical_only = cat.search("prompt injection", k=5, mode="lexical")
    assert {h.id for h in lexical_only} == {"AIR-SEC-010", "AIR-PREV-004"}

    hits = cat.search("prompt injection", k=5)  # default mode="hybrid"
    # A confident lexical top hit (raw BM25 relevance >= 0.9 of the corpus max) stays
    # first in hybrid mode even though a dense re-ranking could disagree.
    assert hits and hits[0].id == lexical_only[0].id

    dense_only = cat.search("prompt injection", k=5, mode="dense")
    assert dense_only and all(h.section is None for h in dense_only)


def test_hybrid_falls_back_to_lexical_when_semantic_unavailable(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("model2vec")
    monkeypatch.setenv("FINOS_MCP_EMBEDDING_MODEL", "/nonexistent/model/path")
    cat = make_catalog()
    assert cat.semantic is None
    assert cat.semantic_status.startswith("disabled:")
    hybrid = cat.search("prompt injection", k=5)
    lexical = cat.search("prompt injection", k=5, mode="lexical")
    assert [h.id for h in hybrid] == [h.id for h in lexical]


# --------------------------------------------------------------- (c) bad model path


def test_bad_embedding_model_path_never_breaks_catalog_build(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FINOS_MCP_EMBEDDING_MODEL", "/nonexistent/path")
    cat = make_catalog()  # must not raise
    assert cat.semantic is None
    assert isinstance(cat.semantic_status, str)
    assert cat.semantic_status.startswith("disabled:")
    # search still works end to end in this state.
    hits = cat.search("prompt injection", k=5)
    assert {h.id for h in hits} == {"AIR-SEC-010", "AIR-PREV-004"}


def test_large_catalog_skips_eager_embedding(clean_env: None) -> None:
    """A catalog with thousands of records (e.g. a large type registry) must not pay an
    unbounded embedding pass just because the `semantic` extra happens to be installed
    -- other servers sharing this module should not get a slow surprise startup."""
    from finos_mcp.core.catalog import _MAX_EAGER_EMBEDDING_DOCS

    big_docs = [
        Document(id=f"D{i}", title=f"Type {i}", body=f"Description of type number {i}.")
        for i in range(_MAX_EAGER_EMBEDDING_DOCS + 1)
    ]
    cat = Catalog(big_docs, kind="type", citation_uri=lambda d: f"test://{d.id}")
    assert cat.semantic is None
    assert "too large" in cat.semantic_status


def test_trivial_query_gets_no_dense_only_hits(clean_env: None) -> None:
    """A dense index always has nearest neighbours, even for "a". With no keyword match and
    no real word in the query, hybrid search must return nothing rather than those."""

    class EverythingIsNear:
        def rank(self, query: str) -> list[tuple[int, float]]:
            return [(i, 0.9) for i in range(len(DOCS))]

    cat = make_catalog()
    cat.semantic = EverythingIsNear()  # type: ignore[assignment]
    assert cat.search("a", k=5, mode="hybrid") == []
    assert cat.search("the", k=5, mode="hybrid") == []
    # a real query still fuses lexical and dense results
    assert cat.search("prompt injection", k=5, mode="hybrid")


def test_dense_mode_without_an_index_falls_back_to_lexical(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FINOS_MCP_SEARCH_MODE=dense with no semantic index used to return nothing at all."""
    cat = make_catalog()
    cat.semantic = None
    monkeypatch.setenv("FINOS_MCP_SEARCH_MODE", " Dense ")  # case and spaces are tolerated
    assert cat.search("prompt injection", k=3)
    assert cat.search("prompt injection", k=0) == []


def test_dense_mode_skips_trivial_queries_and_dissimilar_documents(clean_env: None) -> None:
    class Stub:
        def rank(self, query: str) -> list[tuple[int, float]]:
            return [(0, 0.8), (1, -0.2), (2, -0.9)]

    cat = make_catalog()
    cat.semantic = Stub()  # type: ignore[assignment]
    assert cat.search("a", k=5, mode="dense") == []
    assert len(cat.search("prompt injection", k=5, mode="dense")) == 1


class _FixedRanking:
    """A stand-in dense index that returns one fixed ranking for every query."""

    def __init__(self, ranking: list[tuple[int, float]]) -> None:
        self._ranking = ranking

    def rank(self, query: str) -> list[tuple[int, float]]:
        return list(self._ranking)


def test_hybrid_keeps_the_best_lexical_document_first(clean_env: None) -> None:
    """Measured on the retrieval eval: plain fusion, and every narrower pinning rule tried,
    gave a worse first result than always keeping the lexical winner on top."""
    cat = make_catalog()
    lexical_top = cat.search("allow list MCP servers agents call", k=3, mode="lexical")[0].id
    dense_prefers_others = [(i, 0.9 - 0.1 * n) for n, i in enumerate(reversed(range(len(DOCS))))]
    cat.semantic = _FixedRanking(dense_prefers_others)  # type: ignore[assignment]
    hits = cat.search("allow list MCP servers agents call", k=3, mode="hybrid")
    assert hits[0].id == lexical_top


def test_a_dense_only_hit_reports_its_similarity_not_zero(clean_env: None) -> None:
    cat = make_catalog()
    lexical_ids = {h.id for h in cat.search("allow lists", k=10, mode="lexical")}
    dense_only = next(i for i, d in enumerate(DOCS) if d.id not in lexical_ids)
    cat.semantic = _FixedRanking([(dense_only, 0.6)])  # type: ignore[assignment]
    hits = {h.id: h.score for h in cat.search("allow lists", k=10, mode="hybrid")}
    assert hits[DOCS[dense_only].id] == 0.6


def test_a_query_matching_nothing_gets_no_distant_neighbours(clean_env: None) -> None:
    """With no keyword match, the relative floor alone returned the nearest documents
    however dissimilar: unrelated queries peak around 0.15 with the default model."""
    cat = make_catalog()
    cat.semantic = _FixedRanking([(0, 0.14), (1, 0.08), (2, 0.05)])  # type: ignore[assignment]
    assert cat.search("xyzzy qwerty", k=5, mode="hybrid") == []
    cat.semantic = _FixedRanking([(0, 0.4), (1, 0.3), (2, 0.1)])  # type: ignore[assignment]
    assert [h.id for h in cat.search("xyzzy qwerty", k=5, mode="hybrid")] == [
        DOCS[0].id,
        DOCS[1].id,
    ]
