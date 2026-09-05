"""finos-mcp-cdm: read-only MCP server over the FINOS Common Domain Model.

Type descriptions come from the vendored ``cdm-json-schema`` distribution;
event qualification and root types are extracted from the Rune sources; and
``validate_object`` checks a document in either the Rune (CDM 7) or legacy JSON
shape against the schema, so an agent can verify its own output before use.
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
    Page,
    RateLimit,
    SafetyPolicy,
    SearchHit,
    SourceManifest,
    ValidationReport,
    build_server,
    invalid_input,
    not_found,
    paginate,
    register_server_info,
    register_tool,
)

from . import __version__
from .models import FieldInfo, QualifyFunction, SampleInfo, TypeInfo
from .registry import CdmRegistry, get_registry
from .validate import detect_format
from .validate import validate_object as _validate

VENDOR_DIR = Path(__file__).parent / "_vendor"

INSTRUCTIONS = (
    "Read-only access to the FINOS Common Domain Model (CDM): type definitions from the "
    "published JSON Schema, the product and payout catalogue, business-event qualification "
    "rules, sample documents, and validation of CDM JSON objects in the Rune (CDM 7) or "
    "legacy shape. Typical flow: search_types or list_types to find a type, describe_type "
    "for its fields and cardinality, get_sample for a worked example, then validate_object "
    "on your own document and fix every reported issue. Cite cdm:// resources."
)

PRODUCT_TEMPLATE_TYPES = (
    "NonTransferableProduct",
    "TransferableProduct",
    "TradableProduct",
    "EconomicTerms",
    "Payout",
)


@lru_cache(maxsize=1)
def registry() -> CdmRegistry:
    return get_registry()


@lru_cache(maxsize=1)
def manifest() -> SourceManifest:
    return SourceManifest.load(VENDOR_DIR)


@lru_cache(maxsize=1)
def type_catalog() -> Catalog:
    docs = [
        Document(
            id=t.name,
            title=t.name,
            aliases=[f"{t.namespace}.{t.name}"],
            kind=t.kind,
            body=f"{t.namespace} {t.kind}. {t.description or ''}",
            meta={"namespace": t.namespace},
        )
        for t in registry().types()
    ]
    return Catalog(docs, kind="type", citation_uri=lambda d: f"cdm://schema/{d.id}")


# --------------------------------------------------------------------------- models


class TypeSummary(BaseModel):
    name: str
    namespace: str
    kind: str
    root_type: bool
    description: str | None = None


class TypeDescription(BaseModel):
    name: str
    namespace: str
    kind: str
    description: str | None
    root_type: bool
    extends: str | None
    fields: list[FieldInfo]
    alternatives: list[str] = Field(
        default_factory=list, description="For choice types: the alternative type names."
    )
    used_by: list[str]
    schema_uri: str
    schema_filename: str


class ProductEntry(BaseModel):
    name: str
    role: Literal["template", "payout_alternative"]
    description: str | None = None
    samples: list[str] = Field(default_factory=list)
    schema_uri: str


class Products(BaseModel):
    cdm_version: str
    entries: list[ProductEntry]


class Sample(BaseModel):
    name: str
    format: str
    root_type: str | None
    citation_uri: str
    json_document: dict[str, Any]


class SampleSummary(BaseModel):
    name: str
    format: str
    root_type: str | None
    citation_uri: str


class Samples(BaseModel):
    samples: list[SampleSummary]


class ProductSummary(BaseModel):
    payout_types: list[str]
    identifiers: list[str] = Field(default_factory=list)
    trade_date: str | None = None
    parties: list[str] = Field(default_factory=list)


class EventExplanation(BaseModel):
    qualifier: str | None
    qualify_function: QualifyFunction | None
    format_detected: str | None = None
    instruction_types: list[str] = Field(default_factory=list)
    before_trade_count: int = 0
    after_trade_count: int = 0
    after_products: list[ProductSummary] = Field(default_factory=list)
    sample_uris: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------- tools

Kind = Literal["type", "enum", "choice", "meta"]


def describe_type(name: str) -> TypeDescription:
    """Describe one CDM type by name (TradeState) or fully qualified name
    (cdm.event.common.TradeState): every field with its type and cardinality, choice
    alternatives, which types reference it, and the schema resource to cite."""
    reg = registry()
    info = _type(name)
    alternatives: list[str] = []
    if info.kind == "choice":
        alternatives = sorted(reg.schema_registry.schema(info.filename).get("properties", {}))
    return TypeDescription(
        name=info.name,
        namespace=info.namespace,
        kind=info.kind,
        description=info.description,
        root_type=info.root_type,
        extends=info.extends,
        fields=[] if info.kind == "enum" else reg.fields(info.name),
        alternatives=alternatives,
        used_by=reg.used_by(info.name),
        schema_uri=f"cdm://schema/{info.name}",
        schema_filename=info.filename,
    )


def list_types(
    namespace: str | None = None,
    kind: Kind | None = None,
    root_only: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> Page[TypeSummary]:
    """List CDM types. Filter by namespace prefix (cdm.product), kind (type, enum, choice,
    meta) or root types only (the 16 top-level document types such as TradeState)."""
    if page < 1 or page_size < 1 or page_size > 200:
        raise invalid_input("page must be >= 1 and page_size between 1 and 200.")
    items = [
        TypeSummary(
            name=t.name,
            namespace=t.namespace,
            kind=t.kind,
            root_type=t.root_type,
            description=(t.description or "")[:200] or None,
        )
        for t in registry().types()
        if (namespace is None or t.namespace.startswith(namespace))
        and (kind is None or t.kind == kind)
        and (not root_only or t.root_type)
    ]
    items.sort(key=lambda t: (t.namespace, t.name))
    return paginate(items, page, page_size)


def list_products() -> Products:
    """Catalogue of product types: the product template types (NonTransferableProduct,
    TransferableProduct, TradableProduct, EconomicTerms, Payout) and every Payout
    alternative (InterestRatePayout, CreditDefaultPayout, OptionPayout, ...), with the
    vendored samples that use each."""
    reg = registry()
    entries: list[ProductEntry] = []
    for name in PRODUCT_TEMPLATE_TYPES:
        info = reg.get(name)
        if info is not None:
            entries.append(
                ProductEntry(
                    name=info.name,
                    role="template",
                    description=info.description,
                    schema_uri=f"cdm://schema/{info.name}",
                )
            )
    payout = reg.get("Payout")
    if payout is not None:
        props = reg.schema_registry.schema(payout.filename).get("properties", {})
        usage = _payout_usage()
        for alt in sorted(props):
            entries.append(
                ProductEntry(
                    name=alt,
                    role="payout_alternative",
                    description=props[alt].get("description"),
                    samples=usage.get(alt, []),
                    schema_uri=f"cdm://schema/{alt}",
                )
            )
    return Products(cdm_version=manifest().version or "", entries=entries)


def validate_object(
    object: dict[str, Any],
    type: str | None = None,
    format: Literal["auto", "rune", "legacy"] = "auto",
    schema_version: str | None = None,
) -> ValidationReport:
    """Validate a CDM JSON object against the published schema. The format (Rune with
    '@type'/'@key'/'@ref' keys, or legacy 'value'/'meta' wrappers) is detected unless
    given. The type comes from '@type' or the type argument (e.g. TradeState). Use
    schema_version='6.27.0' for legacy documents produced by CDM 6. Every issue carries
    the JSON path in your document and a kind (required, cardinality, type, enum, ...)."""
    return _validate(registry(), object, type=type, format=format, schema_version=schema_version)


def explain_event(
    event: dict[str, Any] | None = None, qualifier: str | None = None
) -> EventExplanation:
    """Explain a CDM BusinessEvent. Pass the event JSON to read its qualifier, instruction
    kinds, before/after trade states and the products involved; or pass a qualifier name
    (Execution, Termination, ...) to get the Qualify_* rule from the CDM sources and a
    sample that exercises it."""
    reg = registry()
    if event is None and qualifier is None:
        raise invalid_input("Pass event or qualifier.")
    name = qualifier
    explanation = EventExplanation(qualifier=None, qualify_function=None)
    if event is not None:
        if not isinstance(event, dict):
            raise invalid_input("event must be a JSON object.")
        explanation.format_detected = detect_format(event)
        eq = event.get("eventQualifier")
        name = name or (eq if isinstance(eq, str) else None)
        instructions = event.get("instruction") or []
        kinds: list[str] = []
        for ins in instructions if isinstance(instructions, list) else []:
            prim = ins.get("primitiveInstruction") if isinstance(ins, dict) else None
            if isinstance(prim, dict):
                kinds += [k for k in prim if not k.startswith("@")]
            if isinstance(ins, dict) and ins.get("before") is not None:
                explanation.before_trade_count += 1
        explanation.instruction_types = sorted(set(kinds))
        after = event.get("after") or []
        if isinstance(after, list):
            explanation.after_trade_count = len(after)
            explanation.after_products = [
                _product_summary(ts) for ts in after if isinstance(ts, dict)
            ]
        if name is None:
            explanation.notes.append("The event carries no eventQualifier.")
    if name is not None:
        fn = _qualify(name)
        explanation.qualifier = fn.name.removeprefix("Qualify_") if fn else name
        explanation.qualify_function = fn
        if fn is None:
            explanation.notes.append(
                f"No Qualify_* function named {name!r}; see list of qualifiers via cdm://index."
            )
        explanation.sample_uris = [
            f"cdm://sample/{s.name}"
            for s in reg.samples()
            if _sample_qualifier(s) == explanation.qualifier
        ][:5]
    return explanation


def search_types(query: str, k: int = 10) -> list[SearchHit]:
    """Keyword search over CDM type names and descriptions (e.g. 'floating rate payout')."""
    if not query.strip():
        raise invalid_input("query must not be empty.")
    if k < 1 or k > 20:
        raise invalid_input("k must be between 1 and 20.")
    return type_catalog().search(query, k=k)


def get_sample(name: str) -> Sample:
    """Fetch one vendored sample document by name (see list_samples), e.g. a Rune-format
    Execution BusinessEvent for an interest-rate swap, to use as a template."""
    s = _sample(name)
    return Sample(
        name=s.name,
        format=s.format,
        root_type=s.root_type_guess,
        citation_uri=f"cdm://sample/{s.name}",
        json_document=json.loads(Path(s.path).read_text(encoding="utf-8"), strict=False),
    )


def list_samples(format: Literal["rune", "legacy"] | None = None) -> Samples:
    """List the vendored sample documents (Rune-format from CDM 7.2.0, legacy from 6.27.0)."""
    return Samples(
        samples=[
            SampleSummary(
                name=s.name,
                format=s.format,
                root_type=s.root_type_guess,
                citation_uri=f"cdm://sample/{s.name}",
            )
            for s in registry().samples()
            if format is None or s.format == format
        ]
    )


# -------------------------------------------------------------------------- helpers


def _type(name: str) -> TypeInfo:
    info = registry().get(name)
    if info is None:
        hits = type_catalog().search(name, k=3)
        raise not_found(
            "CDM type",
            name,
            hint=("Did you mean " + ", ".join(h.id for h in hits) + "?")
            if hits
            else "Call search_types.",
        )
    return info


def _sample(name: str) -> SampleInfo:
    for s in registry().samples():
        if s.name == name or s.name.removesuffix(".json") == name:
            return s
    raise not_found("sample", name, hint="Call list_samples for names.")


def _qualify(name: str) -> QualifyFunction | None:
    wanted = name.casefold().removeprefix("qualify_")
    for fn in registry().qualify_functions():
        if fn.name.casefold().removeprefix("qualify_") == wanted:
            return fn
    return None


@lru_cache(maxsize=1)
def _sample_qualifiers() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for s in registry().samples():
        try:
            doc = json.loads(Path(s.path).read_text(encoding="utf-8"), strict=False)
        except (OSError, ValueError):
            out[s.name] = None
            continue
        eq = doc.get("eventQualifier") if isinstance(doc, dict) else None
        out[s.name] = eq if isinstance(eq, str) else None
    return out


def _sample_qualifier(s: SampleInfo) -> str | None:
    return _sample_qualifiers().get(s.name)


@lru_cache(maxsize=1)
def _payout_usage() -> dict[str, list[str]]:
    usage: dict[str, list[str]] = {}
    for s in registry().samples():
        try:
            doc = json.loads(Path(s.path).read_text(encoding="utf-8"), strict=False)
        except (OSError, ValueError):
            continue
        for alt in _payout_types(doc):
            usage.setdefault(alt, []).append(s.name)
    return usage


def _payout_types(node: Any, out: set[str] | None = None) -> set[str]:
    """Collect Payout alternative names from Rune ('@type') or legacy (wrapper key) JSON."""
    found: set[str] = set() if out is None else out
    if isinstance(node, dict):
        payout = node.get("payout")
        if isinstance(payout, list):
            for p in payout:
                if isinstance(p, dict):
                    at = p.get("@type")
                    if isinstance(at, str):
                        found.add(at.rsplit(".", 1)[-1])
                    else:
                        found.update(k for k in p if k.endswith("Payout"))
        for v in node.values():
            _payout_types(v, found)
    elif isinstance(node, list):
        for v in node:
            _payout_types(v, found)
    return found


def _product_summary(trade_state: dict[str, Any]) -> ProductSummary:
    raw_trade = trade_state.get("trade")
    trade: dict[str, Any] = raw_trade if isinstance(raw_trade, dict) else trade_state
    ids: list[str] = []
    for tid in trade.get("tradeIdentifier") or []:
        if isinstance(tid, dict):
            for ai in tid.get("assignedIdentifier") or []:
                ident = ai.get("identifier") if isinstance(ai, dict) else None
                if isinstance(ident, dict):
                    v = ident.get("@data", ident.get("value"))
                    if isinstance(v, str):
                        ids.append(v)
                elif isinstance(ident, str):
                    ids.append(ident)
    parties: list[str] = []
    for p in trade.get("party") or []:
        if isinstance(p, dict):
            n = p.get("name")
            v = n.get("@data", n.get("value")) if isinstance(n, dict) else n
            if isinstance(v, str):
                parties.append(v)
    td = trade.get("tradeDate")
    trade_date = td.get("@data", td.get("value")) if isinstance(td, dict) else td
    return ProductSummary(
        payout_types=sorted(_payout_types(trade)),
        identifiers=ids[:10],
        trade_date=trade_date if isinstance(trade_date, str) else None,
        parties=parties[:10],
    )


# --------------------------------------------------------------------------- server


def create_server() -> MCPServer[Any]:
    policy = SafetyPolicy(
        per_tool={
            "validate_object": RateLimit(calls=30, window_s=60, burst=10),
            "explain_event": RateLimit(calls=60, window_s=60, burst=10),
        },
        per_tool_input_bytes={"validate_object": 1024 * 1024, "explain_event": 1024 * 1024},
        max_output_bytes=1024 * 1024,
    )
    server = build_server(
        "finos-mcp-cdm", version=__version__, instructions=INSTRUCTIONS, policy=policy
    )
    for fn in (
        describe_type,
        list_types,
        list_products,
        validate_object,
        explain_event,
        search_types,
        get_sample,
        list_samples,
    ):
        register_tool(server, fn)

    @server.resource(
        "cdm://schema/{type_name}",
        name="cdm_schema",
        title="CDM JSON Schema for one type",
        mime_type="application/schema+json",
    )
    def schema_resource(type_name: str) -> str:
        info = registry().get(type_name)
        if info is None:
            raise ResourceNotFoundError(f"CDM type {type_name!r} not found")
        return json.dumps(registry().schema_registry.schema(info.filename), indent=2)

    @server.resource(
        "cdm://sample/{name}",
        name="cdm_sample",
        title="Vendored CDM sample document",
        mime_type="application/json",
    )
    def sample_resource(name: str) -> str:
        try:
            s = _sample(name)
        except Exception as exc:  # FinosToolError -> resource error
            raise ResourceNotFoundError(f"sample {name!r} not found") from exc
        return Path(s.path).read_text(encoding="utf-8")

    @server.resource(
        "cdm://qualify/{name}",
        name="cdm_qualify",
        title="Event qualification rule (Rune source excerpt)",
        mime_type="text/plain",
    )
    def qualify_resource(name: str) -> str:
        fn = _qualify(name)
        if fn is None:
            raise ResourceNotFoundError(f"no qualification function {name!r}")
        m = manifest()
        return (
            f"# {fn.name} | CDM {m.version} | {m.upstream_repo}@{(m.commit_sha or m.ref)[:12]} | "
            f"rosetta-source/src/main/rosetta/event-qualification-func.rosetta | Community-Spec-1.0\n"
            f"{fn.docstring or ''}\n\ninputs: {fn.inputs}\noutput: {fn.output}\n\n{fn.condition_text}\n"
        )

    @server.resource(
        "cdm://index",
        name="cdm_index",
        title="Index of root types, qualifiers, samples and schema versions",
        mime_type="application/json",
    )
    def index() -> str:
        reg = registry()
        return json.dumps(
            {
                "cdm_version": manifest().version,
                "upstream_commit": manifest().commit_sha,
                "schema_versions": reg.schema_versions(),
                "root_types": reg.root_types(),
                "qualifiers": [f.name for f in reg.qualify_functions()],
                "samples": [s.name for s in reg.samples()],
            },
            indent=2,
        )

    m = manifest()
    reg = registry()
    register_server_info(
        server,
        standard="FINOS Common Domain Model",
        standard_version=m.version,
        upstream_repo=m.upstream_repo,
        upstream_ref=m.ref,
        upstream_commit=m.commit_sha,
        counts=lambda: {
            "schemas": len(reg.schema_registry),
            "schemas_legacy_vintage": sum(
                len(reg.schema_registry_for(v))
                for v in reg.schema_versions()
                if v != reg.PRIMARY_VERSION
            ),
            "types": sum(1 for t in reg.types() if t.kind == "type"),
            "enums": sum(1 for t in reg.types() if t.kind == "enum"),
            "choice_types": sum(1 for t in reg.types() if t.kind == "choice"),
            "root_types": len(reg.root_types()),
            "qualify_functions": len(reg.qualify_functions()),
            "samples": len(reg.samples()),
        },
        resources=lambda: [
            "cdm://schema/{type_name}",
            "cdm://sample/{name}",
            "cdm://qualify/{name}",
            "cdm://index",
        ],
    )
    return server
