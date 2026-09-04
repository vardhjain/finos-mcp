"""In-memory catalog of FDC3 context types and intents, backed by vendored content.

``Fdc3Registry`` loads the vendored context schemas (``_vendor/schemas/context``)
into a `SchemaRegistry` (draft 2019-09, since `context.schema.json` uses the
2019-09 ``unevaluatedProperties`` keyword inside an otherwise draft-07 document
-- see PLAN.md 1.3/6.2) and the generated ``_vendor/intents.json`` into typed
`Intent` models, then cross-links the two so `used_by_intents` and
`intents_for_context` work in both directions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from referencing.exceptions import Unresolvable

from finos_mcp.core import SchemaRegistry, ValidationIssue, ValidationReport, verify

from .models import ContextType, Intent

_VENDOR_DIR = Path(__file__).resolve().parent / "_vendor"
_BASE_SCHEMA_FILENAME = "context.schema.json"
_VERSIONED_ID_SEGMENTS = ("2.2", "2.1")


def _normalize(text: str) -> str:
    """Case-fold and drop non-alphanumerics: 'fdc3.instrument' / 'Instrument' align."""
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def _find_type_const(node: Any) -> str | None:
    """Depth-first search for the first `properties.type.const` in a schema tree."""
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict) and "type" in props:
            type_prop = props["type"]
            if isinstance(type_prop, dict) and isinstance(type_prop.get("const"), str):
                return type_prop["const"]  # type: ignore[no-any-return]
        for value in node.values():
            found = _find_type_const(value)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_type_const(item)
            if found is not None:
                return found
    return None


def _is_experimental(schema: dict[str, Any]) -> bool:
    title = str(schema.get("title") or "")
    description = str(schema.get("description") or "")
    return "experimental" in title.casefold() or "experimental" in description.casefold()


class Fdc3Registry:
    """Typed access to FDC3 context schemas and intents vendored under `_vendor/`."""

    def __init__(self, vendor_dir: Path = _VENDOR_DIR) -> None:
        verify(vendor_dir)
        self._vendor_dir = vendor_dir
        schemas_dir = vendor_dir / "schemas" / "context"

        raw_schemas: dict[str, dict[str, Any]] = {}
        for path in sorted(schemas_dir.glob("*.schema.json")):
            raw_schemas[path.name] = json.loads(path.read_text(encoding="utf-8"))
        self._schemas = SchemaRegistry(raw_schemas, dialect="draft2019-09")

        self._context_types: list[ContextType] = []
        self._type_to_filename: dict[str, str] = {}
        for filename, schema in raw_schemas.items():
            if filename == _BASE_SCHEMA_FILENAME:
                continue  # the base Context type has no `type` const of its own
            type_const = _find_type_const(schema)
            if type_const is None:
                continue
            self._type_to_filename[type_const] = filename
            self._register_aliases(filename, schema, type_const)

            description = schema.get("description")
            self._context_types.append(
                ContextType(
                    type=type_const,
                    title=str(schema.get("title") or filename),
                    filename=filename,
                    experimental=_is_experimental(schema),
                    description=description if isinstance(description, str) else None,
                )
            )
        self._context_types.sort(key=lambda c: c.type)

        self._context_by_norm: dict[str, ContextType] = {}
        for ct in self._context_types:
            filename_stem = ct.filename.removesuffix(".schema.json")
            type_suffix = ct.type.split(".", 1)[-1]
            for key in (ct.type, type_suffix, ct.title, filename_stem):
                self._context_by_norm.setdefault(_normalize(key), ct)

        intents_data = json.loads((vendor_dir / "intents.json").read_text(encoding="utf-8"))
        self._intents: list[Intent] = [Intent(**item) for item in intents_data["intents"]]
        self._intents_by_norm: dict[str, Intent] = {
            _normalize(intent.name): intent for intent in self._intents
        }

        used_by: dict[str, list[str]] = {}
        for intent in self._intents:
            for context_type in intent.contexts:
                used_by.setdefault(context_type, []).append(intent.name)
        for ct in self._context_types:
            ct.used_by_intents = sorted(used_by.get(ct.type, []))

    def _register_aliases(self, filename: str, schema: dict[str, Any], type_const: str) -> None:
        self._schemas.add_alias(filename, filename)
        self._schemas.add_alias(type_const, filename)
        schema_id = schema.get("$id")
        if isinstance(schema_id, str):
            self._schemas.add_alias(schema_id, filename)
            for version in _VERSIONED_ID_SEGMENTS:
                versioned = schema_id.replace("/next/", f"/{version}/")
                if versioned != schema_id:
                    self._schemas.add_alias(versioned, filename)
            # Gotcha (PLAN.md 1.3): `security.user.schema.json`'s `$id` ends in
            # `user.schema.json`, not `security.user.schema.json` -- alias the
            # $id's own basename too so a `$ref` to either form resolves.
            id_basename = schema_id.rsplit("/", 1)[-1]
            if id_basename != filename:
                self._schemas.add_alias(id_basename, filename)

    # ------------------------------------------------------------- contexts
    def context_types(self) -> list[ContextType]:
        return list(self._context_types)

    def get_context(self, type_or_name: str) -> ContextType | None:
        return self._context_by_norm.get(_normalize(type_or_name))

    def schema_for(self, type: str) -> dict[str, Any]:
        ct = self.get_context(type)
        if ct is None:
            raise KeyError(type)
        return self._schemas.schema(ct.filename)

    def example_for(self, type: str) -> dict[str, Any] | None:
        schema = self.schema_for(type)
        examples = schema.get("examples")
        if isinstance(examples, list) and examples and isinstance(examples[0], dict):
            return examples[0]
        return None

    # -------------------------------------------------------------- intents
    def intents(self) -> list[Intent]:
        return list(self._intents)

    def get_intent(self, name: str) -> Intent | None:
        return self._intents_by_norm.get(_normalize(name))

    def intents_for_context(self, type: str) -> list[Intent]:
        ct = self.get_context(type)
        target = ct.type if ct is not None else type
        return [intent for intent in self._intents if target in intent.contexts]

    # ------------------------------------------------------------ validate
    def validate_context(self, obj: dict[str, Any], type: str | None = None) -> ValidationReport:
        resolved_type = type if type is not None else obj.get("type")
        ct = self.get_context(resolved_type) if isinstance(resolved_type, str) else None
        if ct is None:
            return ValidationReport(
                valid=False,
                validator=f"json-schema {self._schemas.dialect}",
                type=resolved_type if isinstance(resolved_type, str) else None,
                issues=[
                    ValidationIssue(json_path="$", message="unknown context type", kind="type")
                ],
            )
        try:
            return self._schemas.validate(obj, ct.filename)
        except Unresolvable as exc:
            # `fdc3.action`'s `app` property `$ref`s `../api/api.schema.json`, part of
            # the FDC3 API/wire schema package we deliberately do not vendor (PLAN.md
            # 1.3 scopes this server to the context schemas only). Report that as a
            # structured issue instead of letting a dangling upstream ref crash a
            # read-only validate call.
            return ValidationReport(
                valid=False,
                validator=f"json-schema {self._schemas.dialect}",
                type=ct.type,
                issues=[
                    ValidationIssue(
                        json_path="$",
                        message=f"schema references an unresolvable external ref: {exc}",
                        kind="reference",
                    )
                ],
                warnings=[f"{ct.filename} refs a schema outside the vendored context set"],
            )

    # -------------------------------------------------------------- counts
    def counts(self) -> dict[str, int]:
        return {
            "intents": len(self._intents),
            "context_types": len(self._context_types),
            "schemas": len(self._schemas),
        }


_registry: Fdc3Registry | None = None


def get_registry() -> Fdc3Registry:
    """Lazily construct and cache the process-wide `Fdc3Registry` singleton."""
    global _registry
    if _registry is None:
        _registry = Fdc3Registry()
    return _registry
