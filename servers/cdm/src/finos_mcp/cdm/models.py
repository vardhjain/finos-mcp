"""Pydantic models for the FINOS Common Domain Model (CDM) type registry.

Shapes follow PLAN.md sections 1.2 and 5.3. ``TypeInfo``/``FieldInfo`` describe
the vendored JSON Schema distribution; ``QualifyFunction`` describes a
``Qualify_*`` event-qualification function extracted from
``event-qualification-func.rosetta``; ``SampleInfo`` describes one vendored
sample document.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TypeKind = Literal["type", "enum", "choice", "meta"]
SampleFormat = Literal["rune", "legacy"]


class FieldInfo(BaseModel):
    """One property of a CDM type, derived from its JSON Schema ``properties``
    entry (unwrapping ``items``/``$ref`` and ``FieldWithMeta*``/``ReferenceWithMeta*``
    meta wrappers)."""

    name: str
    type: str  # referenced TypeName, or a bare JSON type ("string", "boolean", ...)
    cardinality: str  # "1..1" | "0..1" | "0..*" | "1..*" | "m..n"
    description: str | None = None
    is_reference: bool = False  # True for ReferenceWithMeta* wrapped fields
    has_meta: bool = False  # True for FieldWithMeta*/ReferenceWithMeta* wrapped fields
    enum_values: list[str] | None = None


class TypeInfo(BaseModel):
    """One vendored CDM schema file: a type, enum, choice, or meta wrapper."""

    name: str  # "TradeState"
    namespace: str  # "cdm.event.common"
    filename: str  # "cdm-event-common-TradeState.schema.json"
    kind: TypeKind
    description: str | None = None
    root_type: bool = False
    extends: str | None = None

    @property
    def fqn(self) -> str:
        return f"{self.namespace}.{self.name}"


class QualifyFunction(BaseModel):
    """One ``func Qualify_<Name>:`` block from ``event-qualification-func.rosetta``."""

    name: str  # "Qualify_Execution"
    has_business_event_annotation: bool
    docstring: str | None = None
    inputs: list[str] = Field(default_factory=list)  # raw "name Type (card)" strings
    output: str | None = None  # raw "name Type (card)" string
    condition_text: str  # verbatim, trimmed body from "set is_event:"


class SampleInfo(BaseModel):
    """One vendored sample document under ``_vendor/samples/``."""

    name: str  # "execution__execution-basis-swap-func-output.json"
    format: SampleFormat
    root_type_guess: str | None = None
    path: str  # absolute path on disk
