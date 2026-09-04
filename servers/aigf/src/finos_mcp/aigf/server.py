"""finos-mcp-aigf: read-only MCP server over the FINOS AI Governance Framework.

Tools resolve the public ``AIR-<TYPE>-<NNN>`` identifiers the published framework
uses, accept the short ``ri-N`` / ``mi-N`` forms and titles as well, and every
answer carries an ``aigf://`` resource URI an agent can cite.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError
from pydantic import BaseModel, Field

from finos_mcp.core import (
    Catalog,
    Document,
    FinosToolError,
    Page,
    RateLimit,
    SafetyPolicy,
    SearchHit,
    SourceManifest,
    build_server,
    invalid_input,
    not_found,
    paginate,
    register_server_info,
    register_tool,
)

from . import __version__
from .models import (
    Control,
    ControlSummary,
    ExternalRef,
    Framework,
    ReferenceFramework,
    Risk,
    RiskSummary,
)
from .parser import framework_documents, load_framework

VENDOR_DIR = Path(__file__).parent / "_vendor"
CANONICAL_SITE = "https://air-governance-framework.finos.org"

INSTRUCTIONS = (
    "Read-only access to the FINOS AI Governance Framework (AIGF): AI risks and the "
    "controls (mitigations) that address them, with crosswalks to NIST, ISO 42001, the "
    "EU AI Act, OWASP and other references. Identify risks and controls by their public "
    "ids (AIR-SEC-010, AIR-PREV-020); short forms (ri-10, mi-20) and titles also resolve. "
    "Start with search_framework or list_risks, then get_risk / get_control for detail, "
    "map_risks_to_controls for coverage, and cite the aigf:// resource URIs you read."
)

# --------------------------------------------------------------------------- state


@dataclass(slots=True)
class State:
    framework: Framework
    manifest: SourceManifest
    risks: Catalog
    controls: Catalog


@lru_cache(maxsize=1)
def state() -> State:
    fw = load_framework(VENDOR_DIR)
    manifest = SourceManifest.load(VENDOR_DIR)
    risk_docs, control_docs = framework_documents(fw)
    return State(
        framework=fw,
        manifest=manifest,
        risks=Catalog(risk_docs, kind="risk", citation_uri=lambda d: f"aigf://risk/{d.id}"),
        controls=Catalog(
            control_docs, kind="control", citation_uri=lambda d: f"aigf://control/{d.id}"
        ),
    )


def _risk_summary(r: Risk) -> RiskSummary:
    return RiskSummary(
        id=r.id,
        short_id=r.short_id,
        type=r.type,
        title=r.title,
        status=r.status,
        mitigated_by_count=len(r.mitigated_by),
    )


def _control_summary(c: Control) -> ControlSummary:
    return ControlSummary(
        id=c.id,
        short_id=c.short_id,
        type=c.type,
        title=c.title,
        status=c.status,
        mitigates_count=len(c.mitigates),
    )


def _resolve_risk(id: str) -> Risk:
    st = state()
    if st.controls.get(id) is not None and st.risks.get(id) is None:
        raise invalid_input(
            f"{id!r} is a control id, not a risk id.",
            hint="Use get_control for controls (AIR-PREV-*/AIR-DET-*), get_risk for risks.",
        )
    return st.framework.risks[st.risks.resolve(id).id]


def _resolve_control(id: str) -> Control:
    st = state()
    if st.risks.get(id) is not None and st.controls.get(id) is None:
        raise invalid_input(
            f"{id!r} is a risk id, not a control id.",
            hint="Use get_risk for risks (AIR-RC-*/AIR-OP-*/AIR-SEC-*), get_control for controls.",
        )
    return st.framework.controls[st.controls.resolve(id).id]


# --------------------------------------------------------------------------- models


class Edge(BaseModel):
    risk_id: str
    control_id: str


class Mapping(BaseModel):
    risks: list[RiskSummary]
    controls: list[ControlSummary]
    edges: list[Edge]
    uncovered_risks: list[str] = Field(
        default_factory=list, description="Risk ids with no mapped control."
    )
    unresolved: list[str] = Field(
        default_factory=list, description="Inputs that did not resolve to a risk."
    )


class Crosswalk(BaseModel):
    control_id: str
    title: str
    citation_uri: str
    frameworks: list[str]
    refs: list[ExternalRef]


class SearchResults(BaseModel):
    query: str
    scope: str
    hits: list[SearchHit]


class ReferenceFrameworkSummary(BaseModel):
    name: str
    title: str | None = None
    issuer: str | None = None
    url: str | None = None
    entry_count: int
    used_by_risks: int
    used_by_controls: int


class ReferenceFrameworks(BaseModel):
    frameworks: list[ReferenceFrameworkSummary]


class ExternalRefMatch(BaseModel):
    id: str
    kind: Literal["risk", "control"]
    title: str
    framework: str
    key: str
    ref_title: str | None = None
    citation_uri: str


class ExternalRefHits(BaseModel):
    key: str
    framework: str | None = None
    matches: list[ExternalRefMatch]


# ---------------------------------------------------------------------------- tools

RiskType = Literal["RC", "OP", "SEC"]
ControlType = Literal["PREV", "DET"]
Scope = Literal["risks", "controls", "all"]


def list_risks(
    type: RiskType | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> Page[RiskSummary]:
    """List AIGF risks. Filter by type (RC = regulatory and compliance, OP = operational,
    SEC = security) or document status. Returns ids you can pass to get_risk."""
    _check_page(page, page_size)
    fw = state().framework
    items = [
        _risk_summary(r)
        for r in sorted(fw.risks.values(), key=lambda r: r.id)
        if (type is None or r.type == type)
        and (status is None or r.status.casefold() == status.casefold())
    ]
    return paginate(items, page, page_size)


def get_risk(id: str, include_sections: bool = True) -> Risk:
    """Get one AIGF risk by id (AIR-SEC-010, ri-10, 10, or its title), with the controls that
    mitigate it, related risks, and external references. Set include_sections=false for a
    compact record without the full text."""
    risk = _resolve_risk(id)
    return risk if include_sections else risk.model_copy(update={"sections": []})


def list_controls(
    type: ControlType | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> Page[ControlSummary]:
    """List AIGF controls (the framework calls them mitigations). Filter by type
    (PREV = preventative, DET = detective) or status. Returns ids for get_control."""
    _check_page(page, page_size)
    fw = state().framework
    items = [
        _control_summary(c)
        for c in sorted(fw.controls.values(), key=lambda c: c.id)
        if (type is None or c.type == type)
        and (status is None or c.status.casefold() == status.casefold())
    ]
    return paginate(items, page, page_size)


def get_control(id: str, include_sections: bool = True) -> Control:
    """Get one AIGF control by id (AIR-PREV-020, mi-20, 20, or its title), with the risks it
    mitigates, related controls, and crosswalk references (NIST SP 800-53, ISO 42001, ...).
    Set include_sections=false for a compact record."""
    control = _resolve_control(id)
    return control if include_sections else control.model_copy(update={"sections": []})


def map_risks_to_controls(
    risk_ids: list[str] | None = None,
    query: str | None = None,
    k: int = 5,
) -> Mapping:
    """Map risks to the controls that mitigate them. Pass explicit risk_ids (up to 25) or a
    free-text query (the top k matching risks are used). Reports uncovered risks and any
    inputs that did not resolve."""
    st = state()
    fw = st.framework
    if not risk_ids and not query:
        raise invalid_input("Pass risk_ids or query.", hint="e.g. query='prompt injection'")
    if risk_ids and len(risk_ids) > 25:
        raise invalid_input("At most 25 risk_ids per call.", hint="Split the list.")
    if k < 1 or k > 20:
        raise invalid_input("k must be between 1 and 20.")
    resolved: dict[str, Risk] = {}
    unresolved: list[str] = []
    for raw in risk_ids or []:
        try:
            r = _resolve_risk(raw)
        except FinosToolError:
            unresolved.append(raw)
            continue
        resolved[r.id] = r
    if query:
        for hit in st.risks.search(query, k=k):
            resolved.setdefault(hit.id, fw.risks[hit.id])
    controls: dict[str, Control] = {}
    edges: list[Edge] = []
    uncovered: list[str] = []
    for rid in sorted(resolved):
        r = resolved[rid]
        if not r.mitigated_by:
            uncovered.append(rid)
        for cid in r.mitigated_by:
            controls[cid] = fw.controls[cid]
            edges.append(Edge(risk_id=rid, control_id=cid))
    return Mapping(
        risks=[_risk_summary(resolved[i]) for i in sorted(resolved)],
        controls=[_control_summary(controls[i]) for i in sorted(controls)],
        edges=edges,
        uncovered_risks=uncovered,
        unresolved=unresolved,
    )


def map_control_to_external(id: str, frameworks: list[str] | None = None) -> Crosswalk:
    """Crosswalk one control to external frameworks: NIST SP 800-53 r5, NIST AI 600-1,
    ISO 42001, EU AI Act, OWASP LLM/ML/ASI, FFIEC, IOSCO, SR 11-7 and others. Optionally
    restrict to the named frameworks (see list_reference_frameworks)."""
    control = _resolve_control(id)
    wanted = {f.casefold() for f in frameworks} if frameworks else None
    refs = [r for r in control.references if wanted is None or r.framework.casefold() in wanted]
    if wanted is not None:
        known = {f.casefold() for f in state().framework.references}
        unknown = sorted(w for w in wanted if w not in known)
        if unknown:
            raise not_found(
                "reference framework",
                ", ".join(unknown),
                hint="Call list_reference_frameworks for valid names.",
            )
    return Crosswalk(
        control_id=control.id,
        title=control.title,
        citation_uri=control.citation_uri,
        frameworks=sorted({r.framework for r in refs}),
        refs=refs,
    )


def search_framework(query: str, scope: Scope = "all", k: int = 10) -> SearchResults:
    """Full-text search over risks and controls. Each hit has an id, the matching section,
    a snippet, and an aigf:// citation URI. Use scope to limit to risks or controls."""
    if not query.strip():
        raise invalid_input("query must not be empty.")
    if k < 1 or k > 20:
        raise invalid_input("k must be between 1 and 20.")
    st = state()
    hits: list[SearchHit] = []
    if scope in ("risks", "all"):
        hits += st.risks.search(query, k=k)
    if scope in ("controls", "all"):
        hits += st.controls.search(query, k=k)
    hits.sort(key=lambda h: -h.score)
    return SearchResults(query=query, scope=scope, hits=hits[:k])


def list_reference_frameworks() -> ReferenceFrameworks:
    """List the external reference frameworks the AIGF crosswalks to, with entry counts and
    how many risks and controls cite each."""
    fw = state().framework
    risk_use: dict[str, int] = {}
    control_use: dict[str, int] = {}
    for r in fw.risks.values():
        for name in {ref.framework for ref in r.references}:
            risk_use[name] = risk_use.get(name, 0) + 1
    for c in fw.controls.values():
        for name in {ref.framework for ref in c.references}:
            control_use[name] = control_use.get(name, 0) + 1
    out = [
        ReferenceFrameworkSummary(
            name=name,
            title=rf.title,
            issuer=rf.issuer,
            url=rf.url,
            entry_count=len(rf.entries),
            used_by_risks=risk_use.get(name, 0),
            used_by_controls=control_use.get(name, 0),
        )
        for name, rf in sorted(fw.references.items())
    ]
    return ReferenceFrameworks(frameworks=out)


def find_by_external_reference(key: str, framework: str | None = None) -> ExternalRefHits:
    """Reverse crosswalk: find the AIGF risks and controls that cite an external reference,
    e.g. key='sa-9' (NIST SP 800-53), 'llm01-2025' (OWASP LLM Top 10), 'c3-s2-a15' (EU AI
    Act), 'A-6-2-6' (ISO 42001). Matching is case-insensitive and ignores punctuation;
    optionally restrict to one framework name from list_reference_frameworks."""
    if not key.strip():
        raise invalid_input("key must not be empty.")
    fw = state().framework
    if framework is not None and framework not in fw.references:
        raise not_found(
            "reference framework", framework, hint="Call list_reference_frameworks for names."
        )
    wanted = _norm_key(key)
    matches: list[ExternalRefMatch] = []
    records: list[tuple[Literal["risk", "control"], Risk | Control]] = [
        *(("risk", r) for r in fw.risks.values()),
        *(("control", c) for c in fw.controls.values()),
    ]
    for kind, rec in records:
        for ref in rec.references:
            if framework is not None and ref.framework != framework:
                continue
            if _norm_key(ref.key) == wanted:
                matches.append(
                    ExternalRefMatch(
                        id=rec.id,
                        kind=kind,
                        title=rec.title,
                        framework=ref.framework,
                        key=ref.key,
                        ref_title=ref.title,
                        citation_uri=rec.citation_uri,
                    )
                )
    matches.sort(key=lambda m: (m.kind, m.id))
    return ExternalRefHits(key=key, framework=framework, matches=matches)


def _norm_key(key: str) -> str:
    return "".join(ch for ch in key.casefold() if ch.isalnum())


def _check_page(page: int, page_size: int) -> None:
    if page < 1:
        raise invalid_input("page must be >= 1.")
    if page_size < 1 or page_size > 50:
        raise invalid_input("page_size must be between 1 and 50.")


# ------------------------------------------------------------------------ resources


def _raw_markdown(kind: Literal["risk", "control"], id: str) -> tuple[Document, str]:
    st = state()
    catalog = st.risks if kind == "risk" else st.controls
    doc = catalog.get(id)
    if doc is None:
        try:
            doc = catalog.resolve(id)
        except FinosToolError as exc:
            raise ResourceNotFoundError(f"{kind} {id!r} not found") from exc
    record: Risk | Control = (
        st.framework.risks[doc.id] if kind == "risk" else st.framework.controls[doc.id]
    )
    rel = record.source_path.replace("docs/_risks/", "risks/").replace(
        "docs/_mitigations/", "mitigations/"
    )
    text = (VENDOR_DIR / rel).read_text(encoding="utf-8")
    header = (
        f"<!-- {record.id} | {record.title} | FINOS AI Governance Framework "
        f"({st.framework.version}) | upstream {st.manifest.upstream_repo}@"
        f"{(st.manifest.commit_sha or st.manifest.ref)[:12]} | {record.source_path} | "
        f"{CANONICAL_SITE} | CC-BY-4.0 -->\n"
    )
    return doc, header + text


def _index_payload() -> dict[str, Any]:
    fw = state().framework
    return {
        "version": fw.version,
        "release_date": fw.release_date,
        "upstream_commit": fw.upstream_commit,
        "risks": [
            {"id": r.id, "title": r.title, "type": r.type, "mitigated_by": r.mitigated_by}
            for r in sorted(fw.risks.values(), key=lambda r: r.id)
        ],
        "controls": [
            {"id": c.id, "title": c.title, "type": c.type, "mitigates": c.mitigates}
            for c in sorted(fw.controls.values(), key=lambda c: c.id)
        ],
        "reference_frameworks": sorted(fw.references),
    }


def _reference_payload(rf: ReferenceFramework) -> dict[str, Any]:
    return rf.model_dump(mode="json")


# --------------------------------------------------------------------------- server


def create_server() -> MCPServer[Any]:
    policy = SafetyPolicy(
        per_tool={"search_framework": RateLimit(calls=120, window_s=60, burst=20)},
    )
    server = build_server(
        "finos-mcp-aigf", version=__version__, instructions=INSTRUCTIONS, policy=policy
    )

    for fn in (
        list_risks,
        get_risk,
        list_controls,
        get_control,
        map_risks_to_controls,
        map_control_to_external,
        search_framework,
        list_reference_frameworks,
        find_by_external_reference,
    ):
        register_tool(server, fn)

    @server.resource(
        "aigf://risk/{id}",
        name="aigf_risk",
        title="AIGF risk (raw markdown)",
        mime_type="text/markdown",
    )
    def risk_markdown(id: str) -> str:
        return _raw_markdown("risk", id)[1]

    @server.resource(
        "aigf://control/{id}",
        name="aigf_control",
        title="AIGF control (raw markdown)",
        mime_type="text/markdown",
    )
    def control_markdown(id: str) -> str:
        return _raw_markdown("control", id)[1]

    @server.resource(
        "aigf://risk/{id}/section/{slug}",
        name="aigf_risk_section",
        title="One section of an AIGF risk",
        mime_type="text/markdown",
    )
    def risk_section(id: str, slug: str) -> str:
        doc, _ = _raw_markdown("risk", id)
        return _section(doc, slug)

    @server.resource(
        "aigf://control/{id}/section/{slug}",
        name="aigf_control_section",
        title="One section of an AIGF control",
        mime_type="text/markdown",
    )
    def control_section(id: str, slug: str) -> str:
        doc, _ = _raw_markdown("control", id)
        return _section(doc, slug)

    @server.resource(
        "aigf://reference/{framework}",
        name="aigf_reference",
        title="External reference dataset",
        mime_type="application/json",
    )
    def reference_dataset(framework: str) -> str:
        rf = state().framework.references.get(framework)
        if rf is None:
            raise ResourceNotFoundError(f"reference framework {framework!r} not found")
        return json.dumps(_reference_payload(rf), indent=2)

    @server.resource(
        "aigf://index",
        name="aigf_index",
        title="Catalog index of all risks and controls",
        mime_type="application/json",
    )
    def index() -> str:
        return json.dumps(_index_payload(), indent=2)

    @server.prompt(
        name="assess_use_case",
        title="Assess an AI use case against the AIGF",
        description="Identify applicable AIGF risks and the controls that mitigate each, citing ids.",
    )
    def assess_use_case(description: str) -> str:
        return (
            "You are reviewing an AI use case against the FINOS AI Governance Framework.\n"
            f"Use case: {description}\n\n"
            "1. Call search_framework and list_risks to identify the applicable risks.\n"
            "2. Call map_risks_to_controls with those risk ids.\n"
            "3. For each risk, name at least one mitigating control.\n"
            "Cite every risk and control by its AIR-* id and the aigf:// resource you read. "
            "Do not invent ids."
        )

    @server.prompt(
        name="control_gap_analysis",
        title="Gap analysis for controls already in place",
        description="Given controls in place, find risks left uncovered and suggest controls.",
    )
    def control_gap_analysis(controls_in_place: str) -> str:
        return (
            "Controls already in place (AIGF ids or names, comma separated): "
            f"{controls_in_place}\n\n"
            "1. Resolve each with get_control and collect the risks they mitigate.\n"
            "2. Call list_risks and compare: which risks have no control in place?\n"
            "3. For each uncovered risk, call map_risks_to_controls and recommend controls.\n"
            "Cite every id and the aigf:// resources you read."
        )

    def counts() -> dict[str, int]:
        st = state()
        fw = st.framework
        crosswalk = sum(len(r.references) for r in fw.risks.values()) + sum(
            len(c.references) for c in fw.controls.values()
        )
        return {
            "risks": len(fw.risks),
            "controls": len(fw.controls),
            "reference_frameworks": len(fw.references),
            "reference_entries": sum(len(rf.entries) for rf in fw.references.values()),
            "crosswalk_refs": crosswalk,
            "risk_control_edges": sum(len(r.mitigated_by) for r in fw.risks.values()),
        }

    st = state()
    register_server_info(
        server,
        standard="FINOS AI Governance Framework",
        standard_version=st.framework.version,
        upstream_repo=st.manifest.upstream_repo,
        upstream_ref=st.manifest.ref,
        upstream_commit=st.manifest.commit_sha,
        counts=counts,
        resources=lambda: [
            "aigf://risk/{id}",
            "aigf://control/{id}",
            "aigf://risk/{id}/section/{slug}",
            "aigf://control/{id}/section/{slug}",
            "aigf://reference/{framework}",
            "aigf://index",
        ],
    )
    return server


def _section(doc: Document, slug: str) -> str:
    for s in doc.sections:
        if s.slug == slug:
            return f"## {s.heading}\n\n{s.body}\n"
    known = ", ".join(s.slug for s in doc.sections)
    raise ResourceNotFoundError(f"section {slug!r} not found in {doc.id}; known: {known}")
