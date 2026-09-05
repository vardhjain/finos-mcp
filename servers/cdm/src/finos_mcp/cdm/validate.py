"""Validation of CDM JSON objects in both serialisation formats.

The published CDM JSON Schema describes the *legacy* JSON shape (CDM <= 6):
metadata as ``{"value": v, "meta": {...}}``, references as
``{"globalReference": ..., "externalReference": ..., "address": ...}`` and
choice types as an object with exactly one alternative-named property.

CDM 7 documents use the *Rune* JSON shape instead: ``@type`` selects the
alternative (or subtype), ``@scheme``/``@data`` carry scalar metadata,
``@key``/``@key:external``/``@key:scoped`` mark keys and ``@ref``/``@ref:external``/
``@ref:scoped`` are references.  ``finos-cdm``'s Python models would be the
reference validator for Rune JSON, but they take minutes to import and, at
7.2.0, reject their own sample files, so this module instead normalises Rune
JSON into the legacy shape *directed by the schema* and validates that with
Draft 4, mapping every issue path back to the caller's document.

What the schema cannot express is stated in ``ValidationReport.warnings``:
Rune ``condition`` rules and one-of constraints across choice alternatives.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Literal

from finos_mcp.core import ValidationIssue, ValidationReport
from finos_mcp.core.errors import invalid_input, not_found

from .registry import CdmRegistry

Format = Literal["rune", "legacy"]

RUNE_MARKERS = ("@type", "@model", "@version", "@key", "@ref", "@scheme", "@data")
RUNE_CONDITION_WARNING = (
    "Rune `condition` rules and choice-alternative exclusivity are not expressed in the "
    "published JSON Schema and were not checked."
)


def detect_format(obj: Any, *, max_nodes: int = 5000) -> Format:
    """Rune if any object key starts with '@' (checked breadth-first), else legacy."""
    stack: list[Any] = [obj]
    seen = 0
    while stack and seen < max_nodes:
        node = stack.pop()
        seen += 1
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str) and key.startswith("@"):
                    return "rune"
                stack.append(value)
        elif isinstance(node, list):
            stack.extend(node)
    return "legacy"


@dataclass(slots=True)
class _Ctx:
    registry: CdmRegistry
    version: str
    issues: list[ValidationIssue] = field(default_factory=list)
    path_map: dict[str, str] = field(default_factory=dict)  # legacy json path -> rune json path
    nodes: int = 0

    def schema(self, filename: str) -> dict[str, Any]:
        return self.registry.schema_registry_for(self.version).schema(filename)

    def has_schema(self, filename: str) -> bool:
        return filename in self.registry.schema_registry_for(self.version)


def _type_name(filename: str) -> str:
    return filename.removesuffix(".schema.json").rsplit("-", 1)[-1]


def _target_filename(prop: dict[str, Any]) -> tuple[str | None, bool]:
    """Return (referenced schema filename, is_array) for a property schema."""
    if "$ref" in prop:
        return str(prop["$ref"]), False
    if prop.get("type") == "array" and isinstance(prop.get("items"), dict):
        items = prop["items"]
        if "$ref" in items:
            return str(items["$ref"]), True
    return None, prop.get("type") == "array"


def _is_field_with_meta(filename: str) -> bool:
    return "FieldWithMeta" in filename


def _is_reference_with_meta(filename: str) -> bool:
    return "ReferenceWithMeta" in filename


def _is_choice(ctx: _Ctx, filename: str) -> bool:
    info = ctx.registry.get(_type_name(filename))
    return info is not None and info.kind == "choice"


def _choice_chain(
    ctx: _Ctx, choice_file: str, alt: str, depth: int = 4
) -> list[tuple[str, str | None]] | None:
    """Path of (alternative name, schema filename) from a choice type down to `alt`.

    Direct alternatives give a one-element chain; an alternative that is itself a
    choice type is searched recursively (bounded by `depth`).
    """
    props = ctx.schema(choice_file).get("properties", {})
    if alt in props:
        return [(alt, _target_filename(props[alt])[0])]
    if depth <= 0:
        return None
    for name, prop in props.items():
        target, _ = _target_filename(prop)
        if target is not None and ctx.has_schema(target) and _is_choice(ctx, target):
            rest = _choice_chain(ctx, target, alt, depth - 1)
            if rest is not None:
                return [(name, target), *rest]
    return None


def _filename_for_at_type(ctx: _Ctx, at_type: str) -> str | None:
    name = at_type.rsplit(".", 1)[-1]
    info = ctx.registry.get(name)
    if info is None or not ctx.has_schema(info.filename):
        return None
    return info.filename


def _meta_from_keys(node: dict[str, Any]) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if "@scheme" in node:
        meta["scheme"] = node["@scheme"]
    if "@key" in node:
        meta["globalKey"] = node["@key"]
    if "@key:external" in node:
        meta["externalKey"] = node["@key:external"]
    if "@key:scoped" in node:
        meta["key"] = [{"scope": "DOCUMENT", "value": node["@key:scoped"]}]
    return meta


def _reference_from_keys(node: dict[str, Any]) -> dict[str, Any]:
    ref: dict[str, Any] = {}
    if "@ref" in node:
        ref["globalReference"] = node["@ref"]
    if "@ref:external" in node:
        ref["externalReference"] = node["@ref:external"]
    if "@ref:scoped" in node:
        ref["address"] = {"scope": "DOCUMENT", "value": node["@ref:scoped"]}
    return ref


def _plain_keys(node: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in node.items() if not (isinstance(k, str) and k.startswith("@"))}


def _normalize(
    ctx: _Ctx, value: Any, filename: str | None, rune_path: str, legacy_path: str
) -> Any:
    """Convert one Rune node to the legacy shape the schema at `filename` expects."""
    ctx.nodes += 1
    if legacy_path != rune_path:
        ctx.path_map[legacy_path] = rune_path
    if filename is None or not ctx.has_schema(filename):
        return _strip_at_keys(value)

    # ---- metadata-carrying scalar: FieldWithMetaX -----------------------------------
    if _is_field_with_meta(filename):
        if isinstance(value, dict):
            plain = _plain_keys(value)
            inner_schema = ctx.schema(filename).get("properties", {}).get("value", {})
            inner_file, _ = _target_filename(inner_schema)
            if "@data" in value:
                inner = value["@data"]
            elif not plain and any(k.startswith("@ref") for k in value):
                # a reference where a value was expected: keep it, schema will report
                return _reference_from_keys(value)
            else:
                inner = _normalize(ctx, plain, inner_file, rune_path, f"{legacy_path}.value")
            out: dict[str, Any] = {"value": inner}
            meta = _meta_from_keys(value)
            if meta:
                out["meta"] = meta
            ctx.path_map[f"{legacy_path}.value"] = rune_path
            return out
        ctx.path_map[f"{legacy_path}.value"] = rune_path
        return {"value": value}

    # ---- reference: ReferenceWithMetaX ------------------------------------------------
    if _is_reference_with_meta(filename):
        if isinstance(value, dict):
            ref = _reference_from_keys(value)
            plain = _plain_keys(value)
            if plain:
                inner_schema = ctx.schema(filename).get("properties", {}).get("value", {})
                inner_file, _ = _target_filename(inner_schema)
                ref["value"] = _normalize(ctx, plain, inner_file, rune_path, f"{legacy_path}.value")
            meta = _meta_from_keys(value)
            if meta:
                ref["meta"] = meta
            return ref
        return value

    # ---- choice type: wrap under the alternative named by @type ----------------------
    if _is_choice(ctx, filename):
        if not isinstance(value, dict):
            return value
        at_type = value.get("@type")
        if not isinstance(at_type, str):
            ctx.issues.append(
                ValidationIssue(
                    json_path=rune_path,
                    message=f"choice type {_type_name(filename)} requires '@type' to select an alternative",
                    kind="type",
                    validator="rune",
                )
            )
            return _strip_at_keys(value)
        alt = at_type.rsplit(".", 1)[-1]
        chain = _choice_chain(ctx, filename, alt)
        if chain is None:
            choice_props = ctx.schema(filename).get("properties", {})
            ctx.issues.append(
                ValidationIssue(
                    json_path=f"{rune_path}.@type",
                    message=f"{alt!r} is not an alternative of {_type_name(filename)}; "
                    f"expected one of {sorted(choice_props)}",
                    kind="enum",
                    validator="rune",
                )
            )
            return _strip_at_keys(value)
        # Rune names the concrete type; the legacy shape nests one wrapper per choice
        # level, e.g. Underlier -> Product -> NonTransferableProduct.
        leaf_file = chain[-1][1]
        nested_legacy = legacy_path + "".join(f".{name}" for name, _ in chain)
        inner = _normalize(ctx, value, leaf_file, rune_path, nested_legacy)
        for name, _ in reversed(chain):
            inner = {name: inner}
        return inner

    # ---- ordinary data type (possibly with @type naming a subtype) -------------------
    if isinstance(value, dict):
        at_type = value.get("@type")
        if isinstance(at_type, str):
            sub = _filename_for_at_type(ctx, at_type)
            if sub is not None and sub != filename and _is_choice(ctx, sub):
                # declared type is a base; the document picked a choice subtype
                return _normalize(ctx, value, sub, rune_path, legacy_path)
            if sub is not None:
                filename = sub
        schema = ctx.schema(filename)
        props = schema.get("properties", {})
        out = {}
        meta = _meta_from_keys(value)
        for key, child in value.items():
            if isinstance(key, str) and key.startswith("@"):
                continue
            prop = props.get(key)
            child_path = f"{rune_path}.{key}"
            child_legacy = f"{legacy_path}.{key}"
            if not isinstance(prop, dict):
                out[key] = _strip_at_keys(child)
                continue
            target, is_array = _target_filename(prop)
            if is_array and isinstance(child, list):
                out[key] = [
                    _normalize(ctx, item, target, f"{child_path}[{i}]", f"{child_legacy}[{i}]")
                    for i, item in enumerate(child)
                ]
            elif target is not None and not is_array:
                out[key] = _normalize(ctx, child, target, child_path, child_legacy)
            else:
                out[key] = _strip_at_keys(child)
        if meta:
            existing = out.get("meta")
            out["meta"] = {**meta, **existing} if isinstance(existing, dict) else meta
        return out
    if isinstance(value, list):
        return [
            _normalize(ctx, item, filename, f"{rune_path}[{i}]", f"{legacy_path}[{i}]")
            for i, item in enumerate(value)
        ]
    return value


def _strip_at_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: _strip_at_keys(v)
            for k, v in value.items()
            if not (isinstance(k, str) and k.startswith("@"))
        }
    if isinstance(value, list):
        return [_strip_at_keys(v) for v in value]
    return value


def _remap_path(path: str, path_map: dict[str, str]) -> str:
    """Translate a legacy-shape path back to the caller's document via longest prefix."""
    best = ""
    for legacy in path_map:
        if (
            path == legacy or path.startswith(legacy + ".") or path.startswith(legacy + "[")
        ) and len(legacy) > len(best):
            best = legacy
    if not best:
        return path
    return path_map[best] + path[len(best) :]


def resolve_type(registry: CdmRegistry, obj: Any, type: str | None) -> str:
    """Return the TypeName to validate against, from `type` or the document's @type."""
    if type:
        info = registry.get(type)
        if info is None:
            raise not_found("CDM type", type, hint="Call list_types or search_types.")
        return info.name
    if isinstance(obj, dict) and isinstance(obj.get("@type"), str):
        info = registry.get(str(obj["@type"]).rsplit(".", 1)[-1])
        if info is not None:
            return info.name
    raise invalid_input(
        "Cannot infer the CDM type: pass type (e.g. 'TradeState') or include '@type' in the object.",
        hint="Root types: " + ", ".join(registry.root_types()[:8]) + ", ...",
    )


def validate_object(
    registry: CdmRegistry,
    obj: Any,
    *,
    type: str | None = None,
    format: Literal["auto", "rune", "legacy"] = "auto",
    schema_version: str | None = None,
    max_issues: int = 200,
) -> ValidationReport:
    if not isinstance(obj, dict):
        raise invalid_input("object must be a JSON object.")
    version = schema_version or registry.PRIMARY_VERSION
    if version not in registry.schema_versions():
        raise not_found(
            "schema version", version, hint=f"Available: {', '.join(registry.schema_versions())}"
        )
    type_name = resolve_type(registry, obj, type)
    info = registry.get(type_name)
    assert info is not None
    fmt: Format = detect_format(obj) if format == "auto" else format
    schemas = registry.schema_registry_for(version)
    if info.filename not in schemas:
        raise not_found(
            "schema", f"{type_name} in cdm-json-schema {version}", hint="Try the primary version."
        )
    warnings = [RUNE_CONDITION_WARNING]
    ctx = _Ctx(registry=registry, version=version)
    if fmt == "rune":
        instance = _normalize(ctx, copy.deepcopy(obj), info.filename, "$", "$")
        validator_label = f"json-schema draft4 (cdm-json-schema {version}) via Rune normalisation"
    else:
        instance = obj
        validator_label = f"json-schema draft4 (cdm-json-schema {version})"
        if version == registry.PRIMARY_VERSION:
            warnings.append(
                "Legacy-format documents produced by CDM <= 6 may not match the 7.x schema; "
                "pass schema_version='6.27.0' for same-vintage validation."
            )
    report = schemas.validate(instance, info.filename, max_issues=max_issues)
    issues = list(ctx.issues)
    for issue in report.issues:
        issues.append(
            issue.model_copy(update={"json_path": _remap_path(issue.json_path, ctx.path_map)})
            if fmt == "rune"
            else issue
        )
    issues = issues[:max_issues]
    return ValidationReport(
        valid=not issues,
        validator=validator_label,
        type=f"{info.namespace}.{info.name}",
        format_detected=fmt,
        issues=issues,
        warnings=warnings,
        stats={"issues": len(issues), "nodes_normalised": ctx.nodes, "schema_files": len(schemas)},
    )
