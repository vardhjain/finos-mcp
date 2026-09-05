"""Retrieval eval: 50 hand-written questions over the AIGF -> expected ``AIR-*`` ids.

Loads ``aigf_questions.jsonl`` and, for every question, computes a ranked list of ids
two ways:

* ``search_only`` -- just ``search_framework(query=question, k=10)`` (BM25 fused with
  dense semantic search via ``Catalog``'s hybrid mode, when the ``semantic`` extra is
  installed and active; pure BM25 otherwise, or when ``FINOS_MCP_SEARCH_MODE=lexical``
  forces it).
* ``tool_assisted`` -- a tiny "router": ``crosswalk`` questions call
  ``find_by_external_reference`` with the ``key``/``framework`` parsed out of the
  question's ``notes`` field and put those matches first; ``multihop`` questions
  ("both X and Y" style) call ``map_risks_to_controls`` twice -- once with the full
  question as ``query`` (k=3) and, when the question splits into distinct clauses (see
  ``_split_clauses``), once more with those clauses as ``queries`` (k=2) -- and rank the
  mitigating control ids from the combined edges by how many of the matched risks they
  cover (ties broken by id), then the matched risk ids; everything else falls back to
  the same ranked list as ``search_only``. In all cases the plain search hits are
  appended (deduped) so nothing is ever dropped, only re-ranked.

recall@k = |top-k ∩ expected| / |expected|, averaged over questions; MRR uses the rank
of the first expected id in the (deduped) ranked list. Results are written to
``$FINOS_MCP_METRICS_OUT`` (or ``retrieval.json`` in the CWD) in the shape the metrics
collector (``evals/src/finos_mcp_evals/metrics/collect.py``) merges under its top-level
keys.

The recall@5 floors below are deliberately not softened when the suite is red: a
failing run should be fixed by improving ``search_framework`` (chunking, title
boosting, hybrid fusion...) or the questions, never by lowering the bar here. The
non-multihop search-only bar is two-tier: when hybrid search is actually active (per
``search_status``) it must clear 0.85; either way it must clear a 0.78 pure-lexical
floor, so a machine without the optional ``semantic`` extra still gets a real gate.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from collections.abc import AsyncIterator
from pathlib import Path
from statistics import mean
from typing import Any

import anyio
import pytest
from mcp.client import Client
from mcp.shared.exceptions import MCPError

from finos_mcp.aigf.server import create_server

QUESTIONS_PATH = Path(__file__).parent / "aigf_questions.jsonl"

# Targets from PLAN.md 7.3. Do not lower these to make a red run green -- report the
# misses instead so search_framework (or the questions) can be improved.
RECALL_AT_5_SEARCH_ONLY_NON_MULTIHOP_HYBRID_MIN = 0.85
RECALL_AT_5_SEARCH_ONLY_NON_MULTIHOP_LEXICAL_MIN = 0.78
RECALL_AT_5_TOOL_ASSISTED_HYBRID_MIN = 0.90
RECALL_AT_5_TOOL_ASSISTED_LEXICAL_MIN = 0.80

VALID_KINDS = {"direct", "concept", "crosswalk", "multihop"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
AIR_ID_RE = re.compile(r"^AIR-(RC|OP|SEC|PREV|DET)-\d{3}$")
CROSSWALK_NOTES_RE = re.compile(r"key=(\S+)\s+framework=(\S+)")
_BOTH_AND_RE = re.compile(r"\bboth\b(.+?)\band\b(.+)", re.IGNORECASE)
_AND_RE = re.compile(r"\band\b", re.IGNORECASE)


def _load_questions() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with QUESTIONS_PATH.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                raise ValueError(f"{QUESTIONS_PATH}:{lineno}: invalid JSON") from exc
    return rows


QUESTIONS: list[dict[str, Any]] = _load_questions()


# --------------------------------------------------------------------------- metrics


def recall_at_k(results: list[str], expected: set[str], k: int) -> float:
    if not expected:
        return 1.0
    return len(set(results[:k]) & expected) / len(expected)


def reciprocal_rank(results: list[str], expected: set[str]) -> float:
    for i, rid in enumerate(results):
        if rid in expected:
            return 1.0 / (i + 1)
    return 0.0


def _dedupe(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


# ----------------------------------------------------------------------------- client


@pytest.fixture
async def client() -> AsyncIterator[Client]:
    async with Client(create_server(), raise_exceptions=True) as c:
        yield c


async def _call_tool(
    client: Client, name: str, args: dict[str, Any], *, max_retries: int = 20
) -> Any:
    """``client.call_tool`` with backoff on the server's token-bucket rate limiter.

    50 questions issuing back-to-back tool calls in a tight loop comfortably exceeds
    the per-tool burst (search_framework: burst=20; everything else: the server's
    default burst=10), so a bare loop over ``QUESTIONS`` needs to honour the
    ``retry_after_s`` the server reports rather than just hammering it."""
    for _ in range(max_retries):
        try:
            return await client.call_tool(name, args)
        except MCPError as exc:
            retry_after = (
                (exc.data or {}).get("retry_after_s") if isinstance(exc.data, dict) else None
            )
            if retry_after is None:
                raise
            await anyio.sleep(float(retry_after) + 0.02)
    return await client.call_tool(name, args)


async def _search_ids(client: Client, query: str, k: int = 10) -> list[str]:
    result = await _call_tool(client, "search_framework", {"query": query, "scope": "all", "k": k})
    assert result.is_error is False, result.content
    return [h["id"] for h in result.structured_content["hits"]]


def _parse_crosswalk_notes(notes: str) -> tuple[str, str]:
    m = CROSSWALK_NOTES_RE.search(notes)
    assert m, f"crosswalk question notes must contain 'key=... framework=...': {notes!r}"
    return m.group(1), m.group(2)


def _split_clauses(question: str) -> list[str]:
    """Best-effort split of a "both X and Y" / "X, Y, or Z" style question into its
    component clauses, so each concept can be searched on its own instead of blurring
    them into a single BM25/dense query. Tries, in order: 'both ... and ...' (the
    pattern every multihop question in this dataset actually uses), then a plain
    ' and ', then ';'. Clauses under 4 words are dropped as too short to carry a
    useful risk search on their own; at most 5 clauses are returned (the cap
    ``map_risks_to_controls`` places on ``queries``)."""
    q = question.rstrip("?").strip()
    m = _BOTH_AND_RE.search(q)
    if m:
        parts = [m.group(1), m.group(2)]
    elif ";" in q:
        parts = q.split(";")
    elif _AND_RE.search(q):
        parts = _AND_RE.split(q)
    else:
        parts = [q]
    clauses = [p.strip(" ,.;") for p in parts]
    return [c for c in clauses if len(c.split()) >= 4][:5]


async def _tool_assisted_ids(client: Client, q: dict[str, Any], search_ids: list[str]) -> list[str]:
    """Router: crosswalk -> find_by_external_reference, multihop -> map_risks_to_controls,
    everything else -> plain search. ``search_ids`` (already computed once for
    search-only mode) is always appended (deduped) after whatever the specialised tool
    found, so tool-assisted mode is never worse than search-only for a given question,
    and search_framework is never called twice for the same question."""
    kind = q["kind"]

    if kind == "crosswalk":
        key, framework = _parse_crosswalk_notes(q["notes"])
        result = await _call_tool(
            client, "find_by_external_reference", {"key": key, "framework": framework}
        )
        assert result.is_error is False, result.content
        matched = [m["id"] for m in result.structured_content["matches"]]
        return _dedupe(matched + search_ids)

    if kind == "multihop":
        lowered = q["question"].lower()
        control_type: str | None = None
        if "detective" in lowered:
            control_type = "DET"
        elif "preventative" in lowered or "preventive" in lowered:
            control_type = "PREV"

        base_args: dict[str, Any] = {"query": q["question"], "k": 3}
        if control_type:
            base_args["control_type"] = control_type
        result = await _call_tool(client, "map_risks_to_controls", base_args)
        assert result.is_error is False, result.content
        edges = list(result.structured_content["edges"])
        risks = list(result.structured_content["risks"])

        # When the question splits into distinct clauses ("both X and Y"), search each
        # one on its own too -- a single query over the whole question blurs two
        # concepts together and BM25/dense search for the combination often misses one
        # of the two risks entirely.
        clauses = _split_clauses(q["question"])
        if clauses:
            clause_args: dict[str, Any] = {"queries": clauses, "k": 2}
            if control_type:
                clause_args["control_type"] = control_type
            clause_result = await _call_tool(client, "map_risks_to_controls", clause_args)
            assert clause_result.is_error is False, clause_result.content
            edges += clause_result.structured_content["edges"]
            risks += clause_result.structured_content["risks"]

        # Controls that mitigate more of the matched risks rank first -- this is what a
        # "which controls address both/all of these risks" question is really asking.
        control_counts = Counter(e["control_id"] for e in edges)
        controls_ranked = [
            cid for cid, _ in sorted(control_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
        risk_ids = _dedupe([r["id"] for r in risks])
        return _dedupe(controls_ranked + risk_ids + search_ids)

    return search_ids


# ------------------------------------------------------------------------------- test


@pytest.mark.anyio
async def test_retrieval_recall_and_mrr(client: Client) -> None:
    status_result = await _call_tool(client, "search_status", {})
    assert status_result.is_error is False, status_result.content
    status = status_result.structured_content
    semantic_active = bool(status["semantic_enabled"])

    modes = ("search_only", "tool_assisted")
    scores: dict[str, dict[int, list[float]]] = {m: {1: [], 3: [], 5: []} for m in modes}
    rr: dict[str, list[float]] = {m: [] for m in modes}
    non_mh_scores: dict[int, list[float]] = {1: [], 3: [], 5: []}
    non_mh_rr: list[float] = []
    misses: list[dict[str, Any]] = []

    for q in QUESTIONS:
        expected = set(q["expected"])
        search_ids = await _search_ids(client, q["question"], k=10)
        tool_ids = await _tool_assisted_ids(client, q, search_ids)
        ranked = {"search_only": search_ids, "tool_assisted": tool_ids}

        for mode, ids in ranked.items():
            for k in (1, 3, 5):
                scores[mode][k].append(recall_at_k(ids, expected, k))
            rr[mode].append(reciprocal_rank(ids, expected))
            if recall_at_k(ids, expected, 5) < 1.0:
                misses.append(
                    {
                        "id": q["id"],
                        "mode": mode,
                        "kind": q["kind"],
                        "question": q["question"],
                        "expected": sorted(expected),
                        "top5": ids[:5],
                    }
                )

        if q["kind"] != "multihop":
            for k in (1, 3, 5):
                non_mh_scores[k].append(recall_at_k(search_ids, expected, k))
            non_mh_rr.append(reciprocal_rank(search_ids, expected))

    per_mode = {
        mode: {
            "recall_at_1": mean(scores[mode][1]),
            "recall_at_3": mean(scores[mode][3]),
            "recall_at_5": mean(scores[mode][5]),
            "mrr": mean(rr[mode]),
        }
        for mode in modes
    }
    search_only_non_multihop = {
        "recall_at_1": mean(non_mh_scores[1]),
        "recall_at_3": mean(non_mh_scores[3]),
        "recall_at_5": mean(non_mh_scores[5]),
        "mrr": mean(non_mh_rr),
    }

    metrics = {
        "retrieval": {
            "questions": len(QUESTIONS),
            "search_only": per_mode["search_only"],
            "tool_assisted": per_mode["tool_assisted"],
            "search_only_non_multihop": search_only_non_multihop,
            "search_mode": status["mode"],
            "recall_at_5": per_mode["tool_assisted"]["recall_at_5"],
            "mrr": per_mode["tool_assisted"]["mrr"],
            "misses": misses,
        }
    }

    out_path = Path(os.environ.get("FINOS_MCP_METRICS_OUT") or "retrieval.json")
    out_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    search_misses = [m for m in misses if m["mode"] == "search_only"]
    tool_misses = [m for m in misses if m["mode"] == "tool_assisted"]
    non_mh_search_misses = [m for m in search_misses if m["kind"] != "multihop"]

    # Pure-lexical floor: holds whether or not the semantic extra is active.
    assert (
        search_only_non_multihop["recall_at_5"] >= RECALL_AT_5_SEARCH_ONLY_NON_MULTIHOP_LEXICAL_MIN
    ), (
        f"search-only non-multihop recall@5 {search_only_non_multihop['recall_at_5']:.3f} < "
        f"{RECALL_AT_5_SEARCH_ONLY_NON_MULTIHOP_LEXICAL_MIN}; misses:\n"
        + "\n".join(
            f"  {m['id']} ({m['kind']}) expected={m['expected']} top5={m['top5']}"
            for m in non_mh_search_misses
        )
    )
    tool_assisted_min = (
        RECALL_AT_5_TOOL_ASSISTED_HYBRID_MIN
        if semantic_active
        else RECALL_AT_5_TOOL_ASSISTED_LEXICAL_MIN
    )
    assert per_mode["tool_assisted"]["recall_at_5"] >= tool_assisted_min, (
        f"tool-assisted recall@5 {per_mode['tool_assisted']['recall_at_5']:.3f} < "
        f"{tool_assisted_min}; misses:\n"
        + "\n".join(
            f"  {m['id']} ({m['kind']}) expected={m['expected']} top5={m['top5']}"
            for m in tool_misses
        )
    )

    if not semantic_active:
        pytest.skip(
            "semantic search is not active (search_status.semantic_enabled=False; "
            f"semantic_status={status['semantic_status']!r}); only the {RECALL_AT_5_SEARCH_ONLY_NON_MULTIHOP_LEXICAL_MIN} "
            "pure-lexical floor above was asserted, not the hybrid target"
        )
    assert (
        search_only_non_multihop["recall_at_5"] >= RECALL_AT_5_SEARCH_ONLY_NON_MULTIHOP_HYBRID_MIN
    ), (
        f"search-only non-multihop recall@5 {search_only_non_multihop['recall_at_5']:.3f} < "
        f"{RECALL_AT_5_SEARCH_ONLY_NON_MULTIHOP_HYBRID_MIN} with hybrid search active; misses:\n"
        + "\n".join(
            f"  {m['id']} ({m['kind']}) expected={m['expected']} top5={m['top5']}"
            for m in non_mh_search_misses
        )
    )


# ------------------------------------------------------------------------------ sanity


def test_dataset_composition() -> None:
    assert len(QUESTIONS) == 50, f"expected exactly 50 questions, got {len(QUESTIONS)}"

    ids = [q["id"] for q in QUESTIONS]
    assert len(set(ids)) == len(ids), "question ids must be unique"

    kinds = Counter(q["kind"] for q in QUESTIONS)
    difficulties = Counter(q["difficulty"] for q in QUESTIONS)
    assert set(kinds) <= VALID_KINDS, f"unknown kind(s): {set(kinds) - VALID_KINDS}"
    assert set(difficulties) <= VALID_DIFFICULTIES, (
        f"unknown difficulty/ies: {set(difficulties) - VALID_DIFFICULTIES}"
    )
    assert kinds["direct"] == 15, kinds
    assert kinds["concept"] == 15, kinds
    assert kinds["crosswalk"] == 10, kinds
    assert kinds["multihop"] == 10, kinds

    frameworks: set[str] = set()
    for q in QUESTIONS:
        assert 1 <= len(q["expected"]) <= 4, f"{q['id']}: expected must have 1-4 ids"
        for eid in q["expected"]:
            assert AIR_ID_RE.match(eid), f"{q['id']}: {eid!r} is not a valid AIR-* id"
        if q["kind"] == "crosswalk":
            _, framework = _parse_crosswalk_notes(q["notes"])
            frameworks.add(framework)
    assert len(frameworks) >= 8, f"crosswalk questions must span >=8 frameworks, got {frameworks}"


@pytest.mark.anyio
async def test_all_expected_ids_exist(client: Client) -> None:
    index = await client.read_resource("aigf://index")
    payload = json.loads(index.contents[0].text)  # type: ignore[union-attr]
    known = {r["id"] for r in payload["risks"]} | {c["id"] for c in payload["controls"]}
    missing: list[tuple[str, str]] = []
    for q in QUESTIONS:
        for eid in q["expected"]:
            if eid not in known:
                missing.append((q["id"], eid))
    assert not missing, f"expected ids not present in the framework: {missing}"
