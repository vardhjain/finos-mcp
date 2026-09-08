"""Generic document catalog with forgiving id resolution and BM25 search.

Servers load their vendored records into `Document`s and get two things back:

* `resolve(query)` normalises every id form a model might emit and returns
  exactly one document, or raises a structured `not_found` / `ambiguous_id`.
* `search(query, k)` is BM25 over section-level chunks with a fuzzy title boost,
  optionally fused (reciprocal rank fusion) with a dense `SemanticIndex` when the
  `semantic` extra is installed. By default -- no extra installed -- there is no
  embeddings, no model download, sub-second startup.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import bm25s
import Stemmer
from pydantic import BaseModel, Field
from rapidfuzz import fuzz, process

from .errors import FinosToolError, ambiguous, not_found
from .models import SearchHit, Section

_STEMMER = Stemmer.Stemmer("english")

DEFAULT_EMBEDDING_MODEL = "minishlab/potion-base-4M"
_RRF_K = 60
_SEARCH_MODES = ("hybrid", "lexical", "dense")
SearchMode = Literal["hybrid", "lexical", "dense"]
# Embedding every document eagerly at Catalog construction is fine for a few hundred
# short records (AIGF: ~46) but not for a catalog with thousands of entries (e.g. CDM's
# type registry): skip semantic indexing there rather than making every server that
# happens to share this module pay an unbounded embedding pass at startup.
_MAX_EAGER_EMBEDDING_DOCS = 500


def _tokenize(texts: list[str]) -> Any:
    """BM25 tokens with English stopwords removed and Snowball stemming applied."""
    return bm25s.tokenize(texts, stopwords="en", stemmer=_STEMMER, show_progress=False)


_NORM_RE = re.compile(r"[\s_\-./:]+")


def normalize_id(text: str) -> str:
    """Case-fold and strip separators: 'AIR-SEC-010', 'air sec 10', 'air_sec_010' all align."""
    t = _NORM_RE.sub("", text.strip().casefold())
    # collapse zero-padded trailing numbers: airsec010 -> airsec10
    return re.sub(r"(?<=[a-z])0+(\d)", r"\1", t)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")


def split_sections(markdown: str, *, min_level: int = 2) -> list[Section]:
    """Split markdown into sections on '##'-style headings (level >= min_level)."""
    sections: list[Section] = []
    heading: str | None = None
    level = min_level
    buf: list[str] = []
    fence = False

    def flush() -> None:
        body = "\n".join(buf).strip()
        if heading is not None or body:
            sections.append(
                Section(
                    heading=heading or "",
                    slug=slugify(heading) if heading else "preamble",
                    level=level,
                    body=body,
                )
            )

    for line in markdown.splitlines():
        if line.startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m and len(m.group(1)) >= min_level:
            flush()
            heading, level, buf = m.group(2).strip(), len(m.group(1)), []
        else:
            buf.append(line)
    flush()
    return sections


class Document(BaseModel):
    id: str
    title: str
    aliases: list[str] = Field(default_factory=list)
    kind: str = "document"
    body: str = ""
    sections: list[Section] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


@dataclass(slots=True)
class _Chunk:
    doc_index: int
    section: str | None
    text: str


@lru_cache(maxsize=8)
def _load_static_model(model_source: str) -> Any:
    """Load and cache a `model2vec.StaticModel` by name or local path.

    Cached so multiple `Catalog`s (risks, controls, combined, ...) in one process
    share a single loaded model instead of re-downloading/re-loading it each time.
    A failed load is never cached (the exception simply propagates to the caller,
    which retries on the next `Catalog` build)."""
    import os

    from model2vec import StaticModel

    # model2vec defaults to force_download=True, which would re-fetch the model from
    # the Hub on every process start (every server, every test subprocess) even when
    # it is already cached locally -- exactly the network dependency the `semantic`
    # extra's docs promise not to add after the first download. Even with that off,
    # huggingface_hub still checks the remote revision unless told it is offline, so
    # the cached copy is tried offline first and the network is used only on a miss.
    previous = os.environ.get("HF_HUB_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        return StaticModel.from_pretrained(model_source, force_download=False)
    except Exception:
        pass
    finally:
        if previous is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = previous
    return StaticModel.from_pretrained(model_source, force_download=False)


class SemanticIndex:
    """Dense embedding index over whole-document text, built once per `Catalog`.

    Uses `model2vec` static embeddings (pure numpy at inference time, no torch).
    Vectors are L2-normalised so a dot product is a cosine similarity."""

    def __init__(self, model: Any, vectors: Any) -> None:
        self._model = model
        self._vectors = vectors  # shape (n_docs, dim); row i == Catalog._docs[i]

    @classmethod
    def build(cls, docs: list[Document], *, model_name: str) -> SemanticIndex:
        import numpy as np

        model = _load_static_model(model_name)
        if not docs:
            return cls(model, np.zeros((0, 1), dtype=np.float32))
        texts = [f"{d.title} {d.body[:4000]}" for d in docs]
        vectors = np.asarray(model.encode(texts, normalize=True), dtype=np.float32)
        return cls(model, vectors)

    def rank(self, query: str) -> list[tuple[int, float]]:
        """Return every doc index with its cosine similarity to `query`, best first."""
        import numpy as np

        if self._vectors.shape[0] == 0:
            return []
        qv = np.asarray(self._model.encode([query], normalize=True)[0], dtype=np.float32)
        sims = self._vectors @ qv
        order = np.argsort(-sims)
        return [(int(i), float(sims[i])) for i in order]


def _reciprocal_rank_fusion(*rankings: list[int], k: int = _RRF_K) -> list[int]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc_index in enumerate(ranking):
            scores[doc_index] = scores.get(doc_index, 0.0) + 1.0 / (k + rank + 1)
    return [doc_index for doc_index, _ in sorted(scores.items(), key=lambda kv: -kv[1])]


class Catalog:
    def __init__(
        self,
        documents: Iterable[Document],
        *,
        kind: str,
        citation_uri: Callable[[Document], str],
    ) -> None:
        self.kind = kind
        self._docs: list[Document] = list(documents)
        self._citation_uri = citation_uri
        self._by_norm: dict[str, list[int]] = {}
        for i, d in enumerate(self._docs):
            for key in (d.id, *d.aliases):
                self._by_norm.setdefault(normalize_id(key), []).append(i)
        self._title_norm: dict[str, int] = {
            normalize_id(d.title): i for i, d in enumerate(self._docs)
        }
        self._titles = [d.title for d in self._docs]
        self._chunks: list[_Chunk] = []
        for i, d in enumerate(self._docs):
            self._chunks.append(_Chunk(i, None, f"{d.title}\n{d.body}"))
            for s in d.sections:
                if s.body:
                    self._chunks.append(
                        _Chunk(i, s.heading or None, f"{d.title}\n{s.heading}\n{s.body}")
                    )
        self._retriever: bm25s.BM25 | None = None
        if self._chunks:
            tokens = _tokenize([c.text for c in self._chunks])
            self._retriever = bm25s.BM25()
            self._retriever.index(tokens, show_progress=False)
        self.semantic: SemanticIndex | None = None
        self.semantic_status: str = "disabled: not attempted"
        self._build_semantic()

    # ---------------------------------------------------------------- semantic
    def _build_semantic(self) -> None:
        """Best-effort dense index build. Never raises: any failure -- the
        `semantic` extra not installed, no network/no cached model, a bad
        `FINOS_MCP_EMBEDDING_MODEL` -- leaves `self.semantic` as `None` and
        records why in `self.semantic_status`."""
        if len(self._docs) > _MAX_EAGER_EMBEDDING_DOCS:
            self.semantic_status = (
                f"disabled: catalog too large for eager embedding "
                f"({len(self._docs)} docs > {_MAX_EAGER_EMBEDDING_DOCS})"
            )
            return
        model_name = os.environ.get("FINOS_MCP_EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
        try:
            import model2vec  # noqa: F401
        except ImportError:
            self.semantic_status = "disabled: model2vec not installed"
            return
        source = str(Path(model_name)) if Path(model_name).is_dir() else model_name
        try:
            self.semantic = SemanticIndex.build(self._docs, model_name=source)
            self.semantic_status = f"enabled: {model_name}"
        except Exception as exc:  # loading must never break the server
            self.semantic = None
            self.semantic_status = f"disabled: model load failed: {exc}"

    # ------------------------------------------------------------------ access
    def __len__(self) -> int:
        return len(self._docs)

    def __iter__(self) -> Iterable[Document]:
        return iter(self._docs)

    @property
    def documents(self) -> list[Document]:
        return list(self._docs)

    def get(self, id: str) -> Document | None:
        hits = self._by_norm.get(normalize_id(id), [])
        return self._docs[hits[0]] if len(hits) == 1 else None

    def citation_uri(self, doc: Document) -> str:
        return self._citation_uri(doc)

    # ----------------------------------------------------------------- resolve
    def resolve(self, query: str) -> Document:
        """Return exactly one document for an id, alias, or title; else raise a structured error."""
        q = query.strip()
        if not q:
            raise not_found(
                self.kind, query, hint="Pass an id such as the ones returned by list_* tools."
            )
        norm = normalize_id(q)
        exact = self._by_norm.get(norm)
        if exact and len(set(exact)) == 1:
            return self._docs[exact[0]]
        if norm in self._title_norm:
            return self._docs[self._title_norm[norm]]
        # fuzzy title match
        matches = process.extract(q, self._titles, scorer=fuzz.WRatio, limit=5, score_cutoff=60)
        if matches:
            best_score = matches[0][1]
            runner_up = matches[1][1] if len(matches) > 1 else 0.0
            if best_score >= 90 and best_score - runner_up >= 5:
                return self._docs[matches[0][2]]
            candidates = [self._docs[m[2]].id for m in matches]
            raise ambiguous(self.kind, query, candidates)
        raise not_found(
            self.kind,
            query,
            hint=f"Use search to find a {self.kind} by keyword, then call again with its id.",
        )

    def try_resolve(self, query: str) -> Document | None:
        try:
            return self.resolve(query)
        except FinosToolError:
            return None

    # ------------------------------------------------------------------ search
    def search(
        self,
        query: str,
        *,
        k: int = 10,
        predicate: Callable[[Document], bool] | None = None,
        title_boost: float = 0.35,
        mode: SearchMode = "hybrid",
    ) -> list[SearchHit]:
        """Search `query` and return up to `k` hits, best first.

        `mode="lexical"` is exactly today's BM25 + fuzzy-title-boost algorithm.
        `mode="dense"` uses only the `SemanticIndex` (empty if unavailable).
        `mode="hybrid"` (default) reciprocal-rank-fuses the two, except that a
        clearly-confident lexical top hit (its BM25-only relevance, before the
        title boost, is >= 90% of the corpus max) is kept in first place -- a
        strong keyword/title match should not be bumped by a dense disagreement.
        `FINOS_MCP_SEARCH_MODE` (`hybrid`/`lexical`/`dense`) overrides `mode`
        for the whole process, e.g. to force lexical-only for an eval run.
        """
        if not query.strip():
            return []
        env_mode = os.environ.get("FINOS_MCP_SEARCH_MODE")
        if env_mode in _SEARCH_MODES:
            mode = env_mode  # type: ignore[assignment]

        if mode == "dense":
            return self._dense_hits(query, k=k, predicate=predicate)

        lex_n = (
            min(len(self._chunks), max(k * 4, 20))
            if mode == "lexical"
            else min(len(self._chunks), max(k * 8, 50))
        )
        lexical = self._lexical_rank(query, title_boost=title_boost, n=lex_n)
        lex_lookup = {d: (rel, section, text) for d, rel, _raw, section, text in lexical}

        if mode == "lexical" or self.semantic is None:
            order = [d for d, *_ in lexical]
            return self._hits_from_order(order, lex_lookup, query, k=k, predicate=predicate)

        dense_ranked = self.semantic.rank(query)
        # RRF only cares about rank position, not magnitude, so an unfiltered dense
        # ranking would drag in every document in the corpus (cosine similarity is
        # rarely exactly zero for unrelated text the way BM25's term overlap is).
        # Keep only docs at least half as similar as the best dense match.
        dense_floor = 0.5 * dense_ranked[0][1] if dense_ranked else 0.0
        dense_order = [d for d, sim in dense_ranked if sim >= dense_floor]
        lexical_order = [d for d, *_ in lexical]
        fused = _reciprocal_rank_fusion(lexical_order, dense_order)
        if lexical and lexical[0][2] >= 0.9:  # raw (pre-title-boost) BM25 relevance
            top_doc = lexical[0][0]
            fused = [top_doc, *(d for d in fused if d != top_doc)]
        return self._hits_from_order(fused, lex_lookup, query, k=k, predicate=predicate)

    def _lexical_rank(
        self, query: str, *, title_boost: float, n: int
    ) -> list[tuple[int, float, float, str | None, str]]:
        """The BM25 + fuzzy-title-boost algorithm `search(mode="lexical")` has always
        used. Returns `(doc_index, rel, raw_rel, section, text)` sorted by `rel`
        descending; `raw_rel` is the BM25-only component (no title boost)."""
        if self._retriever is None:
            return []
        q_tokens = _tokenize([query])
        n = min(len(self._chunks), max(n, 1))
        try:
            ids, scores = self._retriever.retrieve(q_tokens, k=n, show_progress=False)
        except (ValueError, IndexError):
            return []
        best: dict[int, tuple[float, float, str | None, str]] = {}
        max_score = float(scores[0][0]) if len(scores[0]) and float(scores[0][0]) > 0 else 1.0
        for chunk_id, score in zip(ids[0], scores[0], strict=True):
            s = float(score)
            if s <= 0:
                continue
            chunk = self._chunks[int(chunk_id)]
            raw_rel = s / max_score
            doc = self._docs[chunk.doc_index]
            rel = raw_rel + title_boost * (
                fuzz.partial_ratio(query.casefold(), doc.title.casefold()) / 100.0
            )
            prev = best.get(chunk.doc_index)
            if prev is None or rel > prev[0]:
                best[chunk.doc_index] = (rel, raw_rel, chunk.section, chunk.text)
        # title-only matches for docs BM25 missed entirely
        for title, score, idx in process.extract(
            query, self._titles, scorer=fuzz.partial_ratio, limit=5
        ):
            if idx not in best and score >= 85:
                best[idx] = (
                    title_boost * score / 100.0,
                    0.0,
                    None,
                    f"{title}\n{self._docs[idx].body[:300]}",
                )
        return [
            (doc_index, rel, raw_rel, section, text)
            for doc_index, (rel, raw_rel, section, text) in sorted(
                best.items(), key=lambda kv: -kv[1][0]
            )
        ]

    def _dense_hits(
        self, query: str, *, k: int, predicate: Callable[[Document], bool] | None
    ) -> list[SearchHit]:
        if self.semantic is None:
            return []
        hits: list[SearchHit] = []
        for doc_index, sim in self.semantic.rank(query):
            doc = self._docs[doc_index]
            if predicate is not None and not predicate(doc):
                continue
            text = f"{doc.title}\n{doc.body[:300]}"
            hits.append(
                SearchHit(
                    id=doc.id,
                    title=doc.title,
                    section=None,
                    score=round(sim, 4),
                    snippet=_snippet(text, query),
                    citation_uri=self._citation_uri(doc),
                )
            )
            if len(hits) >= k:
                break
        return hits

    def _hits_from_order(
        self,
        order: list[int],
        lex_lookup: dict[int, tuple[float, str | None, str]],
        query: str,
        *,
        k: int,
        predicate: Callable[[Document], bool] | None,
    ) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for doc_index in order:
            doc = self._docs[doc_index]
            if predicate is not None and not predicate(doc):
                continue
            if doc_index in lex_lookup:
                rel, section, text = lex_lookup[doc_index]
            else:
                rel, section, text = 0.0, None, f"{doc.title}\n{doc.body[:300]}"
            hits.append(
                SearchHit(
                    id=doc.id,
                    title=doc.title,
                    section=section,
                    score=round(rel, 4),
                    snippet=_snippet(text, query),
                    citation_uri=self._citation_uri(doc),
                )
            )
            if len(hits) >= k:
                break
        return hits


def _snippet(text: str, query: str, width: int = 240) -> str:
    body = " ".join(text.split())
    terms = [t for t in re.findall(r"\w+", query.casefold()) if len(t) > 2]
    low = body.casefold()
    pos = min((low.find(t) for t in terms if low.find(t) >= 0), default=-1)
    if pos < 0:
        return body[:width] + ("…" if len(body) > width else "")
    start = max(0, pos - width // 3)
    end = min(len(body), start + width)
    return ("…" if start > 0 else "") + body[start:end] + ("…" if end < len(body) else "")
