"""finos-mcp-fdc3: read-only MCP server over the FDC3 standard.

Exposes the standard intents, the context-type JSON schemas, validation of a
context object, and intent suggestion for a given context.  Everything comes
from content vendored at a pinned FDC3 release; ``fdc3://`` resources serve the
raw schema and intent documentation for citation.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError
from pydantic import BaseModel, Field

from finos_mcp.core import (
    Catalog,
    Document,
    RateLimit,
    SafetyPolicy,
    SearchHit,
    SourceManifest,
    ValidationReport,
    build_server,
    invalid_input,
    not_found,
    register_server_info,
    register_tool,
)

from . import __version__
from .models import ContextType, Intent
from .registry import Fdc3Registry, get_registry

VENDOR_DIR = Path(__file__).parent / "_vendor"
SCHEMA_ID_BASE = "https://fdc3.finos.org/schemas"

INSTRUCTIONS = (
    "Read-only access to the FINOS FDC3 standard: the standard intents (ViewChart, "
    "ViewInstrument, StartChat, ...), the context-type JSON schemas (fdc3.instrument, "
    "fdc3.contact, ...), validation of context objects, and intent suggestion for a context. "
    "Use list_intents / list_context_types to discover names, get_context_schema for the "
    "exact shape, validate_context before raising an intent, and suggest_intent to choose "
    "one. Cite fdc3:// resources when quoting the standard."
)


@lru_cache(maxsize=1)
def registry() -> Fdc3Registry:
    return get_registry()


@lru_cache(maxsize=1)
def manifest() -> SourceManifest:
    return SourceManifest.load(VENDOR_DIR)


@lru_cache(maxsize=1)
def intent_catalog() -> Catalog:
    docs = [
        Document(
            id=i.name,
            title=i.name,
            aliases=[i.title],
            kind="intent",
            body=f"{i.description} Contexts: {', '.join(i.contexts)}. Result: {i.result or 'none'}.",
        )
        for i in registry().intents()
    ]
    return Catalog(docs, kind="intent", citation_uri=lambda d: f"fdc3://intent/{d.id}")


# --------------------------------------------------------------------------- models


class IntentSummary(BaseModel):
    name: str
    contexts: list[str]
    result: str | None = None
    deprecated: bool
    citation_uri: str


class Intents(BaseModel):
    fdc3_version: str | None
    intents: list[IntentSummary]


class ContextTypeSummary(BaseModel):
    type: str
    title: str
    experimental: bool
    used_by_intents: list[str]
    schema_uri: str


class ContextTypes(BaseModel):
    fdc3_version: str | None
    context_types: list[ContextTypeSummary]


class PropertySummary(BaseModel):
    name: str
    type: str | None = None
    required: bool
    description: str | None = None


class ContextSchema(BaseModel):
    type: str
    title: str
    schema_id: str | None
    schema_uri: str
    required: list[str]
    properties: list[PropertySummary]
    example: dict[str, Any] | None = None
    json_schema: dict[str, Any] = Field(description="The vendored JSON Schema document.")


class IntentSuggestion(BaseModel):
    name: str
    score: float
    reason: str
    result: str | None = None
    deprecated: bool
    citation_uri: str


class IntentSuggestions(BaseModel):
    context_type: str | None
    detected_by: Literal["type_field", "structural_match", "explicit"]
    suggestions: list[IntentSuggestion]
    validation: ValidationReport | None = None


# ---------------------------------------------------------------------------- tools


def list_intents(include_deprecated: bool = True, context_type: str | None = None) -> Intents:
    """List the standard FDC3 intents with the context types each accepts and the result
    type it returns, if any. Filter to intents that accept one context_type (e.g.
    fdc3.instrument)."""
    reg = registry()
    if context_type is not None:
        ct = reg.get_context(context_type)
        if ct is None:
            raise not_found("context type", context_type, hint="Call list_context_types.")
        intents = reg.intents_for_context(ct.type)
    else:
        intents = reg.intents()
    out = [
        _summary(i)
        for i in sorted(intents, key=lambda i: i.name)
        if include_deprecated or not i.deprecated
    ]
    return Intents(fdc3_version=manifest().version, intents=out)


def get_intent(name: str) -> Intent:
    """Get one intent by name (case-insensitive): accepted contexts, result type, description,
    deprecation status, and the fdc3:// resource holding its reference documentation."""
    intent = registry().get_intent(name)
    if intent is None:
        hits = intent_catalog().search(name, k=3)
        raise not_found(
            "intent",
            name,
            hint=f"Did you mean {', '.join(h.id for h in hits)}?" if hits else "Call list_intents.",
        )
    return intent


def list_context_types(experimental: bool | None = None) -> ContextTypes:
    """List the FDC3 context types (fdc3.instrument, fdc3.contact, ...), whether each is
    experimental, and which intents accept it."""
    types = registry().context_types()
    if experimental is not None:
        types = [t for t in types if t.experimental == experimental]
    return ContextTypes(
        fdc3_version=manifest().version,
        context_types=[
            ContextTypeSummary(
                type=t.type,
                title=t.title,
                experimental=t.experimental,
                used_by_intents=t.used_by_intents,
                schema_uri=t.schema_uri,
            )
            for t in sorted(types, key=lambda t: t.type)
        ],
    )


def get_context_schema(type: str) -> ContextSchema:
    """Get the JSON Schema for a context type (by type such as fdc3.instrument, or by name
    such as Instrument), with a summary of required and optional properties and the
    standard example."""
    ct = _context(type)
    schema = registry().schema_for(ct.type)
    return ContextSchema(
        type=ct.type,
        title=ct.title,
        schema_id=schema.get("$id"),
        schema_uri=ct.schema_uri,
        required=_flatten(schema)[1],
        properties=_properties(schema),
        example=registry().example_for(ct.type),
        json_schema=schema,
    )


def validate_context(context: dict[str, Any], type: str | None = None) -> ValidationReport:
    """Validate a context object against its FDC3 schema. The type is read from the object's
    `type` field unless given explicitly. Issues carry a JSON path and a kind (required,
    type, enum, unknown_field, ...)."""
    if not isinstance(context, dict):
        raise invalid_input("context must be a JSON object.")
    target = type or context.get("type")
    if not isinstance(target, str) or not target:
        raise invalid_input(
            "The context has no `type` field; pass type explicitly.",
            hint="e.g. type='fdc3.instrument'",
        )
    ct = registry().get_context(target)
    if ct is None:
        raise not_found("context type", target, hint="Call list_context_types.")
    return registry().validate_context(context, ct.type)


def suggest_intent(
    context: dict[str, Any] | None = None,
    context_type: str | None = None,
    goal: str | None = None,
) -> IntentSuggestions:
    """Suggest which intents to raise for a context. Pass the context object (its `type` is
    used; if missing or unknown the object is matched structurally against every schema),
    or a context_type. An optional goal ("show a price chart") re-ranks by description."""
    reg = registry()
    if context is None and context_type is None:
        raise invalid_input("Pass context or context_type.")
    detected: Literal["type_field", "structural_match", "explicit"]
    validation: ValidationReport | None = None
    resolved: str | None = None
    if context_type is not None:
        ct = reg.get_context(context_type)
        if ct is None:
            raise not_found("context type", context_type, hint="Call list_context_types.")
        resolved, detected = ct.type, "explicit"
    else:
        assert context is not None
        declared = context.get("type")
        ct = reg.get_context(declared) if isinstance(declared, str) else None
        if ct is not None:
            resolved, detected = ct.type, "type_field"
            validation = reg.validate_context(context, ct.type)
        else:
            resolved, detected = _structural_match(context), "structural_match"
    suggestions: list[IntentSuggestion] = []
    if resolved is not None:
        for intent in reg.intents_for_context(resolved):
            score = 1.0 if intent.name.lower().endswith(resolved.split(".")[-1].lower()) else 0.8
            if intent.deprecated:
                score -= 0.3
            suggestions.append(
                IntentSuggestion(
                    name=intent.name,
                    score=round(score, 3),
                    reason=f"{intent.name} accepts {resolved}",
                    result=intent.result,
                    deprecated=intent.deprecated,
                    citation_uri=intent.citation_uri,
                )
            )
    if goal:
        boost = {h.id: h.score for h in intent_catalog().search(goal, k=10)}
        for s in suggestions:
            if s.name in boost:
                s.score = round(s.score + 0.5 * boost[s.name], 3)
                s.reason += f"; matches goal {goal!r}"
    suggestions.sort(key=lambda s: (-s.score, s.name))
    return IntentSuggestions(
        context_type=resolved, detected_by=detected, suggestions=suggestions, validation=validation
    )


def find_intents_by_context(context_type: str) -> Intents:
    """FDC3-API-style alias of list_intents(context_type=...): the intents that accept a
    context type."""
    return list_intents(context_type=context_type)


def search_intents(query: str, k: int = 5) -> list[SearchHit]:
    """Keyword search over intent names and descriptions."""
    if not query.strip():
        raise invalid_input("query must not be empty.")
    if k < 1 or k > 20:
        raise invalid_input("k must be between 1 and 20.")
    return intent_catalog().search(query, k=k)


# -------------------------------------------------------------------------- helpers


def _summary(i: Intent) -> IntentSummary:
    return IntentSummary(
        name=i.name,
        contexts=i.contexts,
        result=i.result,
        deprecated=i.deprecated,
        citation_uri=i.citation_uri,
    )


def _context(type_or_name: str) -> ContextType:
    ct = registry().get_context(type_or_name)
    if ct is None:
        raise not_found("context type", type_or_name, hint="Call list_context_types.")
    return ct


def _flatten(schema: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Merge `properties` and `required` across the top level and `allOf` parts.

    FDC3 context schemas put their own properties in ``allOf[0]`` and reference the
    base context in ``allOf[1]``, so the top-level keys alone are empty.
    """
    props: dict[str, Any] = {}
    required: list[str] = []
    for part in [schema, *schema.get("allOf", [])]:
        if isinstance(part, dict):
            props.update(part.get("properties", {}) or {})
            for name in part.get("required", []) or []:
                if name not in required:
                    required.append(name)
    return props, required


def _properties(schema: dict[str, Any]) -> list[PropertySummary]:
    props, required = _flatten(schema)
    out: list[PropertySummary] = []
    for name, spec in props.items():
        if not isinstance(spec, dict):
            continue
        t = spec.get("type")
        if t is None and "$ref" in spec:
            t = f"$ref {spec['$ref']}"
        if t is None and "const" in spec:
            t = f"const {spec['const']!r}"
        out.append(
            PropertySummary(
                name=name,
                type=t if isinstance(t, str) else (", ".join(t) if isinstance(t, list) else None),
                required=name in required,
                description=spec.get("description") or spec.get("title"),
            )
        )
    return out


def _structural_match(context: dict[str, Any]) -> str | None:
    """Pick the context type whose schema the object violates least (ties: fewest props)."""
    reg = registry()
    probe = dict(context)
    best: tuple[int, str] | None = None
    for ct in reg.context_types():
        probe["type"] = ct.type
        report = reg.validate_context(probe, ct.type)
        issues = len(report.issues)
        if best is None or issues < best[0]:
            best = (issues, ct.type)
    return best[1] if best and best[0] == 0 else None


# --------------------------------------------------------------------------- server


def create_server() -> MCPServer[Any]:
    policy = SafetyPolicy(
        per_tool={
            "validate_context": RateLimit(calls=120, window_s=60, burst=20),
            "suggest_intent": RateLimit(calls=120, window_s=60, burst=20),
        },
        per_tool_input_bytes={"validate_context": 256 * 1024, "suggest_intent": 256 * 1024},
    )
    server = build_server(
        "finos-mcp-fdc3", version=__version__, instructions=INSTRUCTIONS, policy=policy
    )
    for fn in (
        list_intents,
        get_intent,
        list_context_types,
        get_context_schema,
        validate_context,
        suggest_intent,
        find_intents_by_context,
        search_intents,
    ):
        register_tool(server, fn)

    @server.resource(
        "fdc3://schema/{type}",
        name="fdc3_schema",
        title="FDC3 context schema (raw JSON Schema)",
        mime_type="application/schema+json",
    )
    def schema_resource(type: str) -> str:
        ct = registry().get_context(type)
        if ct is None:
            raise ResourceNotFoundError(f"context type {type!r} not found")
        return json.dumps(registry().schema_for(ct.type), indent=2)

    @server.resource(
        "fdc3://intent/{name}",
        name="fdc3_intent",
        title="FDC3 intent reference documentation (raw markdown)",
        mime_type="text/markdown",
    )
    def intent_resource(name: str) -> str:
        intent = registry().get_intent(name)
        if intent is None:
            raise ResourceNotFoundError(f"intent {name!r} not found")
        path = VENDOR_DIR / "intents" / Path(intent.doc_path).name
        m = manifest()
        header = (
            f"<!-- {intent.name} | FDC3 {m.version} | upstream {m.upstream_repo}@"
            f"{(m.commit_sha or m.ref)[:12]} | {intent.doc_path} | Community-Spec-1.0 -->\n"
        )
        return header + path.read_text(encoding="utf-8")

    @server.resource(
        "fdc3://intents",
        name="fdc3_intents_table",
        title="Generated intent-to-context table",
        mime_type="application/json",
    )
    def intents_table() -> str:
        return (VENDOR_DIR / "intents.json").read_text(encoding="utf-8")

    @server.resource(
        "fdc3://index",
        name="fdc3_index",
        title="Index of context types and intents",
        mime_type="application/json",
    )
    def index() -> str:
        reg = registry()
        return json.dumps(
            {
                "fdc3_version": manifest().version,
                "upstream_commit": manifest().commit_sha,
                "context_types": [t.type for t in reg.context_types()],
                "intents": [
                    {"name": i.name, "contexts": i.contexts, "result": i.result}
                    for i in reg.intents()
                ],
            },
            indent=2,
        )

    m = manifest()
    register_server_info(
        server,
        standard="FINOS FDC3",
        standard_version=m.version,
        upstream_repo=m.upstream_repo,
        upstream_ref=m.ref,
        upstream_commit=m.commit_sha,
        counts=lambda: registry().counts(),
        resources=lambda: [
            "fdc3://schema/{type}",
            "fdc3://intent/{name}",
            "fdc3://intents",
            "fdc3://index",
        ],
    )
    return server
