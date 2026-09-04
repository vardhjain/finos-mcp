"""Pydantic models for the FDC3 intent and context-type catalog."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator


class Intent(BaseModel):
    """A standardized (or docs-only) FDC3 intent, as parsed from `_vendor/intents.json`."""

    name: str
    title: str
    contexts: list[str] = Field(default_factory=list)
    result: str | None = None
    deprecated: bool = False
    standard: bool = True
    since: str | None = None
    description: str = ""
    doc_path: str
    citation_uri: str = ""

    @model_validator(mode="after")
    def _default_citation_uri(self) -> Self:
        if not self.citation_uri:
            self.citation_uri = f"fdc3://intent/{self.name}"
        return self


class ContextType(BaseModel):
    """An FDC3 context data type, as indexed from a vendored context schema."""

    type: str
    title: str
    filename: str
    experimental: bool = False
    schema_uri: str = ""
    description: str | None = None
    used_by_intents: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _default_schema_uri(self) -> Self:
        if not self.schema_uri:
            self.schema_uri = f"fdc3://schema/{self.type}"
        return self
