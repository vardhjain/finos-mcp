"""Generic document catalog with forgiving id resolution and BM25 search.

Servers load their vendored records into `Document`s and get two things back:

* `resolve(query)` normalises every id form a model might emit and returns
  exactly one document, or raises a structured `not_found` / `ambiguous_id`.
* `search(query, k)` is BM25 over section-level chunks with a fuzzy title boost.
  No embeddings, no model download, sub-second startup.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import bm25s
from pydantic import BaseModel, Field
from rapidfuzz import fuzz, process

from .errors import FinosToolError, ambiguous, not_found
from .models import SearchHit, Section

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
            self._chunks.append(_Chunk(i, None, f"{d.title}\n{d.body[:2000]}"))
            for s in d.sections:
                if s.body:
                    self._chunks.append(
                        _Chunk(i, s.heading or None, f"{d.title}\n{s.heading}\n{s.body}")
                    )
        self._retriever: bm25s.BM25 | None = None
        if self._chunks:
            tokens = bm25s.tokenize(
                [c.text for c in self._chunks], stopwords="en", show_progress=False
            )
            self._retriever = bm25s.BM25()
            self._retriever.index(tokens, show_progress=False)

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
    ) -> list[SearchHit]:
        if self._retriever is None or not query.strip():
            return []
        q_tokens = bm25s.tokenize([query], stopwords="en", show_progress=False)
        # bm25s returns ids/scores shaped (1, n); clamp n to corpus size.
        n = min(len(self._chunks), max(k * 4, 20))
        try:
            ids, scores = self._retriever.retrieve(q_tokens, k=n, show_progress=False)
        except (ValueError, IndexError):
            return []
        best: dict[int, tuple[float, str | None, str]] = {}
        max_score = float(scores[0][0]) if len(scores[0]) and float(scores[0][0]) > 0 else 1.0
        for chunk_id, score in zip(ids[0], scores[0], strict=True):
            s = float(score)
            if s <= 0:
                continue
            chunk = self._chunks[int(chunk_id)]
            rel = s / max_score
            doc = self._docs[chunk.doc_index]
            rel += title_boost * (
                fuzz.partial_ratio(query.casefold(), doc.title.casefold()) / 100.0
            )
            prev = best.get(chunk.doc_index)
            if prev is None or rel > prev[0]:
                best[chunk.doc_index] = (rel, chunk.section, chunk.text)
        # title-only matches for docs BM25 missed entirely
        for title, score, idx in process.extract(
            query, self._titles, scorer=fuzz.partial_ratio, limit=5
        ):
            if idx not in best and score >= 85:
                best[idx] = (
                    title_boost * score / 100.0,
                    None,
                    f"{title}\n{self._docs[idx].body[:300]}",
                )
        hits: list[SearchHit] = []
        for doc_index, (rel, section, text) in sorted(best.items(), key=lambda kv: -kv[1][0]):
            doc = self._docs[doc_index]
            if predicate is not None and not predicate(doc):
                continue
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
