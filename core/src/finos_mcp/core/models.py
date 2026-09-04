"""Shared Pydantic models used across servers."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Section(BaseModel):
    heading: str
    slug: str
    level: int = 2
    body: str


class Page[T](BaseModel):
    items: list[T]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)

    @property
    def has_more(self) -> bool:
        return self.page * self.page_size < self.total


def paginate[T](items: list[T], page: int, page_size: int) -> Page[T]:
    start = (page - 1) * page_size
    return Page[T](
        items=items[start : start + page_size], page=page, page_size=page_size, total=len(items)
    )


class SearchHit(BaseModel):
    id: str
    title: str
    section: str | None = None
    score: float
    snippet: str
    citation_uri: str


class Citation(BaseModel):
    id: str
    title: str
    uri: str
    source_path: str
    upstream_commit: str | None = None
    canonical_url: str | None = None


IssueKind = Literal[
    "required",
    "cardinality",
    "type",
    "enum",
    "unknown_field",
    "format",
    "condition",
    "reference",
    "other",
]


class ValidationIssue(BaseModel):
    json_path: str
    message: str
    kind: IssueKind = "other"
    validator: str | None = None
    schema_path: str | None = None


class ValidationReport(BaseModel):
    valid: bool
    validator: str
    type: str | None = None
    format_detected: str | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)


class ServerInfo(BaseModel):
    name: str
    version: str
    standard: str
    standard_version: str | None = None
    upstream_repo: str | None = None
    upstream_ref: str | None = None
    upstream_commit: str | None = None
    read_only: Literal[True] = True
    counts: dict[str, int] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    latency: dict[str, Any] = Field(default_factory=dict)
    policy: dict[str, Any] = Field(default_factory=dict)
