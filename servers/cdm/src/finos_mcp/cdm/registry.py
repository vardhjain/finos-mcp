"""Lazily-built, in-memory index over the vendored CDM JSON Schema distribution.

Every vendored vintage is bundled as a single
``_vendor/schemas/cdm-json-schema-<version>.json`` file (``{"version", "source",
"count", "schemas": {filename: schema, ...}}``) rather than one file per
schema, so ``CdmRegistry`` reads that bundle once, strips the non-standard
top-level ``$anchor`` key CDM emits (draft-04 has no ``$anchor``; see PLAN.md
1.2) from each schema, and builds a ``finos_mcp.core.SchemaRegistry`` over the
result for validation plus a name/namespace/reverse-reference index for
browsing. ``get_registry()`` exposes this as a process-wide lazy singleton so
every tool call reuses the same parsed index.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

from finos_mcp.core import SchemaRegistry, verify

from .models import FieldInfo, QualifyFunction, SampleInfo, TypeInfo, TypeKind

CDM_PKG_DIR = Path(__file__).resolve().parent
DEFAULT_VENDOR_DIR = CDM_PKG_DIR / "_vendor"

_META_PREFIXES = ("FieldWithMeta", "ReferenceWithMeta")

_JSON_SCHEMA_TYPES = frozenset(
    {"object", "array", "string", "number", "integer", "boolean", "null"}
)


def _drop_bogus_type_keywords(node: Any) -> None:
    """Work around a cdm-json-schema 7.2.0 generator defect: a handful of
    property schemas (``ValuationTime``, ``CreditEventNotice``, ...) emit a
    literal Rosetta basictype name as the JSON Schema ``"type"`` keyword --
    e.g. ``{"type": "BusinessCenter"}`` or ``{"type": "NonNegativeNumber"}` --
    instead of a JSON primitive or a ``$ref``. Neither name has a matching
    schema file (they are Rosetta ``basicType``s the generator should have
    resolved to ``string``/``number``), so ``Draft4Validator`` hard-crashes
    with ``jsonschema.exceptions.UnknownType`` the moment it tries to type-check
    a real instance value there. This mutates ``node`` in place, dropping any
    such non-standard ``type`` keyword so that property is merely unconstrained
    (rather than un-validatable) -- confirmed narrow: 9 + 5 occurrences across
    1139 vendored schema files at the time this was written."""
    if isinstance(node, dict):
        type_value = node.get("type")
        if isinstance(type_value, str) and type_value not in _JSON_SCHEMA_TYPES:
            del node["type"]
        for value in node.values():
            _drop_bogus_type_keywords(value)
    elif isinstance(node, list):
        for item in node:
            _drop_bogus_type_keywords(item)


def _bundle_path_for(vendor_dir: Path, version: str) -> Path:
    """Path to the single-file bundle vendoring one CDM JSON Schema vintage,
    e.g. ``_vendor/schemas/cdm-json-schema-7.2.0.json``."""
    return vendor_dir / "schemas" / f"cdm-json-schema-{version}.json"


def _load_schema_bundle(bundle_path: Path) -> dict[str, dict[str, Any]]:
    """Load every schema out of a ``cdm-json-schema-<version>.json`` bundle
    (written by ``scripts/sync_upstream.py`` via ``json.dumps``, so it is
    always strict-parseable JSON even though a couple of source members
    needed lenient parsing to ingest -- see the bundle's ``lenient_parse``
    key), applying the same fix-ups (drop the non-standard ``$anchor`` key;
    drop bogus Rosetta-basictype ``"type"`` keywords) regardless of vendored
    vintage, since both defects are generator artifacts of ``cdm-json-schema``
    and not specific to 7.2.0."""
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    schemas: dict[str, dict[str, Any]] = {}
    for name, data in bundle["schemas"].items():
        data.pop("$anchor", None)
        _drop_bogus_type_keywords(data)
        schemas[name] = data
    return schemas


def _strip_type_prefix(name: str) -> str:
    for prefix in _META_PREFIXES:
        if name.startswith(prefix) and len(name) > len(prefix):
            return name[len(prefix) :]
    return name


def _parse_filename(filename: str) -> tuple[str, str]:
    """Split ``cdm-event-common-TradeState.schema.json`` into
    (``"cdm.event.common"``, ``"TradeState"``)."""
    stem = filename.removesuffix(".schema.json")
    parts = stem.split("-")
    namespace = ".".join(parts[:-1])
    name = parts[-1]
    return namespace, name


def _cardinality(prop: dict[str, Any], *, required: bool) -> str:
    if prop.get("type") == "array":
        lo = prop.get("minItems", 0)
        hi = prop.get("maxItems")
        return f"{lo}..{hi if hi is not None else '*'}"
    return "1..1" if required else "0..1"


class CdmRegistry:
    #: The version whose schemas back type indexing (`types()`, `get()`,
    #: `fields()`, `used_by()`) and the default `schema_registry` property.
    #: Vendored at ``_vendor/schemas/``.
    PRIMARY_VERSION = "7.2.0"

    def __init__(self, vendor_dir: Path = DEFAULT_VENDOR_DIR) -> None:
        self.vendor_dir = vendor_dir
        verify(vendor_dir)

        bundle_path = _bundle_path_for(vendor_dir, self.PRIMARY_VERSION)
        schemas = _load_schema_bundle(bundle_path)
        self._schema_registry = SchemaRegistry(schemas, dialect="draft4")
        self._raw_schemas = schemas
        # Lazily-populated cache of `SchemaRegistry` instances for every
        # non-primary vendored vintage (e.g. "6.27.0"), keyed by version string.
        self._schema_registries_by_version: dict[str, SchemaRegistry] = {
            self.PRIMARY_VERSION: self._schema_registry
        }

        choice_data = json.loads((vendor_dir / "choice_types.json").read_text(encoding="utf-8"))
        self._choice_names: set[str] = {c["name"] for c in choice_data["choice_types"]}

        root_data = json.loads((vendor_dir / "root_types.json").read_text(encoding="utf-8"))
        self._root_types: list[dict[str, Any]] = root_data["root_types"]
        root_index: dict[tuple[str, str], dict[str, Any]] = {
            (r["namespace"], r["name"]): r for r in self._root_types
        }

        qualify_data = json.loads((vendor_dir / "qualify.json").read_text(encoding="utf-8"))
        self._qualify_functions = [QualifyFunction(**f) for f in qualify_data["functions"]]

        types: dict[str, TypeInfo] = {}  # filename -> TypeInfo
        by_name: dict[str, list[str]] = {}  # lowercase name -> [filenames]
        by_fqn: dict[str, str] = {}  # lowercase "namespace.name" -> filename

        for filename, schema in schemas.items():
            namespace, name = _parse_filename(filename)
            root_entry = root_index.get((namespace, name))
            kind: TypeKind
            if "enum" in schema:
                kind = "enum"
            elif name in self._choice_names:
                kind = "choice"
            elif name.startswith(_META_PREFIXES) or filename.startswith(
                "com-rosetta-model-metafields-"
            ):
                kind = "meta"
            else:
                kind = "type"

            info = TypeInfo(
                name=name,
                namespace=namespace,
                filename=filename,
                kind=kind,
                description=schema.get("description"),
                root_type=root_entry is not None,
                extends=root_entry.get("extends") if root_entry else None,
            )
            types[filename] = info
            by_name.setdefault(name.lower(), []).append(filename)
            by_fqn[f"{namespace}.{name}".lower()] = filename

        self._types = types
        self._by_name = by_name
        self._by_fqn = by_fqn

        # Reverse-reference index: filename -> set of filenames that $ref it.
        reverse: dict[str, set[str]] = {fn: set() for fn in schemas}
        for filename, schema in schemas.items():
            for ref in _iter_refs(schema):
                if ref in reverse:
                    reverse[ref].add(filename)
        self._used_by = reverse

        samples_dir = vendor_dir / "samples"
        self._samples = _load_samples(samples_dir)

    # -- schema access --------------------------------------------------

    @property
    def schema_registry(self) -> SchemaRegistry:
        """The primary (``PRIMARY_VERSION``) JSON Schema registry."""
        return self._schema_registry

    def schema_versions(self) -> list[str]:
        """Every vendored JSON Schema vintage, primary version first (e.g.
        ``["7.2.0", "6.27.0"]``), discovered from the
        `_vendor/schemas/cdm-json-schema-<version>.json` bundle files actually
        present on disk."""
        prefix, suffix = "cdm-json-schema-", ".json"
        found = sorted(
            path.name.removeprefix(prefix).removesuffix(suffix)
            for path in (self.vendor_dir / "schemas").glob(f"{prefix}*{suffix}")
        )
        return [self.PRIMARY_VERSION] + [v for v in found if v != self.PRIMARY_VERSION]

    def schema_registry_for(self, version: str = PRIMARY_VERSION) -> SchemaRegistry:
        """The JSON Schema registry for one vendored vintage. Lazy and cached
        per version: the primary registry is built in `__init__`; every other
        vintage (e.g. ``"6.27.0"``, vendored at
        `_vendor/schemas/cdm-json-schema-6.27.0.json`) is parsed on first
        request and reused afterwards. Legacy-format samples only validate
        meaningfully against a schema of matching vintage (see PLAN.md 1.2) --
        the primary 7.2.0 schema describes a different JSON shape entirely."""
        cached = self._schema_registries_by_version.get(version)
        if cached is not None:
            return cached
        bundle_path = _bundle_path_for(self.vendor_dir, version)
        if not bundle_path.is_file():
            raise ValueError(
                f"unknown CDM schema version {version!r}: no {bundle_path} bundle. "
                f"Vendored versions: {self.schema_versions()}"
            )
        schemas = _load_schema_bundle(bundle_path)
        registry = SchemaRegistry(schemas, dialect="draft4")
        self._schema_registries_by_version[version] = registry
        return registry

    def types(self) -> list[TypeInfo]:
        return sorted(self._types.values(), key=lambda t: (t.namespace, t.name))

    def get(self, name_or_fqn: str) -> TypeInfo | None:
        key = name_or_fqn.strip()
        if "." in key:
            filename = self._by_fqn.get(key.lower())
            if filename:
                return self._types[filename]
            # fall through: maybe a bare name that happens to contain no dot check failed
        matches = self._by_name.get(key.lower())
        if not matches:
            return None
        return self._types[sorted(matches)[0]]

    def fields(self, name: str) -> list[FieldInfo]:
        info = self.get(name)
        if info is None:
            raise KeyError(name)
        schema = self._raw_schemas[info.filename]
        properties: dict[str, Any] = schema.get("properties", {})
        required = set(schema.get("required", []))

        fields: list[FieldInfo] = []
        for prop_name, prop in properties.items():
            fields.append(self._field_info(prop_name, prop, required=prop_name in required))
        return fields

    def _field_info(self, prop_name: str, prop: dict[str, Any], *, required: bool) -> FieldInfo:
        description = prop.get("description")
        cardinality = _cardinality(prop, required=required)

        target = prop
        if prop.get("type") == "array" and "items" in prop:
            target = prop["items"]

        ref = target.get("$ref")
        if ref is None:
            json_type = target.get("type", "object")
            return FieldInfo(
                name=prop_name,
                type=str(json_type),
                cardinality=cardinality,
                description=description,
                enum_values=target.get("enum"),
            )

        ref_info = self._types.get(ref)
        ref_schema = self._raw_schemas.get(ref)

        if (
            ref_info is not None
            and ref_info.kind == "meta"
            and ref_info.name.startswith(_META_PREFIXES)
        ):
            unwrapped = _strip_type_prefix(ref_info.name)
            is_reference = ref_info.name.startswith("ReferenceWithMeta")
            return FieldInfo(
                name=prop_name,
                type=unwrapped,
                cardinality=cardinality,
                description=description,
                is_reference=is_reference,
                has_meta=True,
            )

        enum_values = ref_schema.get("enum") if ref_schema else None
        return FieldInfo(
            name=prop_name,
            type=ref_info.name if ref_info is not None else ref.removesuffix(".schema.json"),
            cardinality=cardinality,
            description=description,
            enum_values=enum_values,
        )

    def used_by(self, name: str) -> list[str]:
        info = self.get(name)
        if info is None:
            return []
        referrers = self._used_by.get(info.filename, set())
        return sorted(self._types[fn].name for fn in referrers)

    def root_types(self) -> list[str]:
        return sorted({r["name"] for r in self._root_types})

    def qualify_functions(self) -> list[QualifyFunction]:
        return list(self._qualify_functions)

    def samples(self) -> list[SampleInfo]:
        return list(self._samples)


def _iter_refs(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            yield ref
        for value in node.values():
            yield from _iter_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_refs(item)


def _root_type_guess(data: Any) -> str | None:
    if isinstance(data, dict):
        type_value = data.get("@type")
        if isinstance(type_value, str):
            return type_value.rsplit(".", 1)[-1]
    return None


def _load_samples(samples_dir: Path) -> list[SampleInfo]:
    samples: list[SampleInfo] = []
    rune_dir = samples_dir / "rune"
    if rune_dir.is_dir():
        for path in sorted(rune_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"), strict=False)
            samples.append(
                SampleInfo(
                    name=path.name,
                    format="rune",
                    root_type_guess=_root_type_guess(data),
                    path=str(path),
                )
            )
    legacy_dir = samples_dir / "legacy"
    if legacy_dir.is_dir():
        for path in sorted(legacy_dir.glob("*.json")):
            samples.append(
                SampleInfo(
                    name=path.name,
                    format="legacy",
                    root_type_guess="BusinessEvent",
                    path=str(path),
                )
            )
    return samples


@lru_cache(maxsize=1)
def get_registry() -> CdmRegistry:
    return CdmRegistry()
