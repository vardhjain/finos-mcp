"""JSON Schema registry that resolves sibling-filename and `$id` references.

CDM schemas use bare relative filenames in `$ref` and declare draft-04; FDC3
schemas use absolute `$id`s and draft-07 with a 2019-09 keyword.  One registry
class serves both by keying every resource under its filename *and* its `$id`.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft4Validator, Draft7Validator, Draft201909Validator, Draft202012Validator
from jsonschema.exceptions import ValidationError
from jsonschema.protocols import Validator
from referencing import Registry, Resource
from referencing import jsonschema as ref_js
from referencing.exceptions import NoSuchResource

from .models import IssueKind, ValidationIssue, ValidationReport

Dialect = Literal["draft4", "draft7", "draft2019-09", "draft2020-12"]

_VALIDATORS: dict[Dialect, type[Validator]] = {
    "draft4": Draft4Validator,
    "draft7": Draft7Validator,
    "draft2019-09": Draft201909Validator,
    "draft2020-12": Draft202012Validator,
}
_SPECS = {
    "draft4": ref_js.DRAFT4,
    "draft7": ref_js.DRAFT7,
    "draft2019-09": ref_js.DRAFT201909,
    "draft2020-12": ref_js.DRAFT202012,
}

_KIND_BY_VALIDATOR: dict[str, IssueKind] = {
    "required": "required",
    "minItems": "cardinality",
    "maxItems": "cardinality",
    "minProperties": "cardinality",
    "maxProperties": "cardinality",
    "type": "type",
    "enum": "enum",
    "const": "enum",
    "additionalProperties": "unknown_field",
    "unevaluatedProperties": "unknown_field",
    "format": "format",
    "pattern": "format",
    "$ref": "reference",
}


class SchemaRegistry:
    def __init__(self, schemas: dict[str, dict[str, Any]], *, dialect: Dialect) -> None:
        self.dialect = dialect
        self._schemas = schemas  # filename -> schema
        spec = _SPECS[dialect]
        self._by_key: dict[str, dict[str, Any]] = {}
        for fname, schema in schemas.items():
            self._by_key[fname] = schema
            sid = schema.get("$id") or schema.get("id")
            if isinstance(sid, str):
                self._by_key[sid] = schema
                self._by_key[sid.rsplit("/", 1)[-1]] = schema

        def retrieve(uri: str) -> Resource[Any]:
            schema = self._by_key.get(uri) or self._by_key.get(uri.rsplit("/", 1)[-1])
            if schema is None:
                raise NoSuchResource(uri)
            return Resource.from_contents(schema, default_specification=spec)

        self._registry: Registry[Any] = Registry(retrieve=retrieve)  # type: ignore[call-arg]
        self._validator_cls = _VALIDATORS[dialect]

    @classmethod
    def from_directory(
        cls, path: Path, *, dialect: Dialect, pattern: str = "*.json"
    ) -> SchemaRegistry:
        schemas: dict[str, dict[str, Any]] = {}
        for p in sorted(path.glob(pattern)):
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                schemas[p.name] = data
        return cls(schemas, dialect=dialect)

    def add_alias(self, alias: str, filename: str) -> None:
        self._by_key[alias] = self._schemas[filename]

    @property
    def filenames(self) -> list[str]:
        return sorted(self._schemas)

    def schema(self, key: str) -> dict[str, Any]:
        schema = self._by_key.get(key) or self._by_key.get(key.rsplit("/", 1)[-1])
        if schema is None:
            raise KeyError(key)
        return schema

    def __contains__(self, key: str) -> bool:
        return key in self._by_key or key.rsplit("/", 1)[-1] in self._by_key

    def __len__(self) -> int:
        return len(self._schemas)

    @lru_cache(maxsize=4096)  # noqa: B019 - registry instances are long-lived singletons
    def validator(self, key: str) -> Validator:
        schema = self.schema(key)
        # A file with $id/id is resolved relative to that base; otherwise relative to nothing,
        # which makes bare sibling filenames resolve through `retrieve` (CDM style).
        return self._validator_cls(schema, registry=self._registry)

    def iter_issues(self, instance: Any, key: str) -> Iterable[ValidationIssue]:
        validator = self.validator(key)
        for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
            yield issue_from_error(err)

    def validate(self, instance: Any, key: str, *, max_issues: int = 200) -> ValidationReport:
        issues: list[ValidationIssue] = []
        for issue in self.iter_issues(instance, key):
            issues.append(issue)
            if len(issues) >= max_issues:
                break
        return ValidationReport(
            valid=not issues,
            validator=f"json-schema {self.dialect}",
            type=key,
            issues=issues,
            stats={"issues": len(issues)},
        )


def issue_from_error(err: ValidationError) -> ValidationIssue:
    keyword = err.validator or ""
    kind: IssueKind = _KIND_BY_VALIDATOR.get(str(keyword), "other")
    return ValidationIssue(
        json_path=err.json_path,
        message=err.message if len(err.message) < 500 else err.message[:497] + "...",
        kind=kind,
        validator=str(keyword) or None,
        schema_path="/".join(str(p) for p in err.absolute_schema_path) or None,
    )
