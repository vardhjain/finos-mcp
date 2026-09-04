"""Pydantic models for the FINOS AI Governance Framework (AIGF).

Shapes follow PLAN.md sections 1.1 and 4.2. Public ids are derived, not present in
upstream frontmatter: ``AIR-{type}-{sequence:03d}`` (e.g. ``AIR-SEC-010``); the
upstream short id (``ri-10`` / ``mi-20``) is kept alongside it as ``short_id``.
Upstream ``doc-status`` values (``Pre-Draft``, ``Draft``, ``Working-Group-Approved``,
``Approved-Specification``) are passed through as plain ``str`` rather than a
``Literal`` so a new upstream status does not break parsing.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from finos_mcp.core import Section

RiskType = Literal["RC", "OP", "SEC"]
ControlType = Literal["PREV", "DET"]


class ExternalRef(BaseModel):
    """One entry in a ``<dataset>_references`` frontmatter list, resolved against
    the vendored dataset in ``_vendor/references/<framework>.yml``."""

    framework: str  # dataset name, e.g. "nist-sp-800-53r5"
    key: str  # entry key within the dataset, e.g. "sa-9"
    title: str | None = None
    url: str | None = None
    issuer: str | None = None


class Risk(BaseModel):
    id: str  # "AIR-SEC-010"
    short_id: str  # "ri-10"
    sequence: int
    type: RiskType
    type_label: str  # "Security"
    title: str
    status: str
    summary: str
    sections: list[Section] = Field(default_factory=list)
    related_risks: list[str] = Field(default_factory=list)  # AIR-* ids
    mitigated_by: list[str] = Field(default_factory=list)  # AIR-PREV-*/AIR-DET-* ids
    references: list[ExternalRef] = Field(default_factory=list)
    source_path: str  # "docs/_risks/ri-10_prompt-injection.md"
    citation_uri: str  # "aigf://risk/AIR-SEC-010"


class Control(BaseModel):
    """AIGF calls these "mitigations"; we expose both words."""

    id: str  # "AIR-PREV-020"
    short_id: str  # "mi-20"
    sequence: int
    type: ControlType
    type_label: str  # "Preventative"
    title: str
    status: str
    summary: str
    sections: list[Section] = Field(default_factory=list)
    mitigates: list[str] = Field(default_factory=list)  # AIR-* risk ids
    related_controls: list[str] = Field(default_factory=list)  # AIR-PREV-*/AIR-DET-* ids
    references: list[ExternalRef] = Field(default_factory=list)
    source_path: str  # "docs/_mitigations/mi-20_mcp-server-security-governance.md"
    citation_uri: str  # "aigf://control/AIR-PREV-020"


class RiskSummary(BaseModel):
    id: str
    short_id: str
    type: RiskType
    title: str
    status: str
    mitigated_by_count: int


class ControlSummary(BaseModel):
    id: str
    short_id: str
    type: ControlType
    title: str
    status: str
    mitigates_count: int


class ReferenceEntry(BaseModel):
    key: str
    title: str | None = None
    url: str | None = None
    description: str | None = None
    issuer: str | None = None


class ReferenceFramework(BaseModel):
    name: str  # dataset filename stem, e.g. "nist-sp-800-53r5"
    title: str | None = None
    issuer: str | None = None
    url: str | None = None
    entries: dict[str, ReferenceEntry] = Field(default_factory=dict)


class Framework(BaseModel):
    version: str
    release_date: str | None = None
    upstream_commit: str | None = None
    risks: dict[str, Risk] = Field(default_factory=dict)  # keyed by AIR id
    controls: dict[str, Control] = Field(default_factory=dict)  # keyed by AIR id
    references: dict[str, ReferenceFramework] = Field(default_factory=dict)  # keyed by dataset name
    type_labels: dict[str, str] = Field(
        default_factory=dict
    )  # "RC"/"OP"/"SEC"/"PREV"/"DET" -> label
