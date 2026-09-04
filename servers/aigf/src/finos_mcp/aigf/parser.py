"""Parse the vendored FINOS AI Governance Framework content into typed models.

``load_framework()`` reads ``_vendor/risks/*.md``, ``_vendor/mitigations/*.md``,
``_vendor/references/*.yml`` and ``_vendor/_config.yml`` (written by
``scripts/sync_upstream.py``) and returns a fully cross-linked :class:`Framework`.

Upstream quirks this parser is written to tolerate (see PLAN.md sections 1.1 and
4.2, and the parser test for the exact numbers on the current vendored snapshot):

* Public ids (``AIR-SEC-010``) are not in frontmatter; they are derived from
  ``type`` + ``sequence``.
* Risk -> control linkage is one-way in the source (only mitigations carry
  ``mitigates:``); ``Risk.mitigated_by`` is computed here by inversion.
* ``<dataset>_references`` lists carry inline ``# comment`` annotations, which is
  ordinary YAML and requires no special handling from ``yaml.safe_load``.
* A handful of upstream risk files have a missing newline between the last
  ``uk-regulations_references`` entry's comment and a following ``related_risks:``
  key, which folds ``related_risks:`` and its items into the YAML comment and
  leaves stray ``ri-N`` tokens inside ``uk-regulations_references``. Those tokens
  simply fail to resolve against the uk-regulations dataset and are kept as
  unresolved ``ExternalRef``s (title/url/issuer left ``None``), exactly like any
  other reference key the dataset does not define.
"""

from __future__ import annotations

from pathlib import Path

import frontmatter
import yaml

from finos_mcp.core import Document, Section, split_sections, verify

from .models import (
    Control,
    ControlType,
    ExternalRef,
    Framework,
    ReferenceEntry,
    ReferenceFramework,
    Risk,
    RiskType,
)

_REFERENCES_SUFFIX = "_references"


def _default_vendor_dir() -> Path:
    return Path(__file__).parent / "_vendor"


def _summary_and_sections(body: str) -> tuple[str, list[Section]]:
    sections = split_sections(body)
    for section in sections:
        if section.body.strip():
            return section.body.strip(), sections
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    return (paragraphs[0] if paragraphs else ""), sections


def _load_reference_frameworks(vendor_dir: Path) -> dict[str, ReferenceFramework]:
    frameworks: dict[str, ReferenceFramework] = {}
    references_dir = vendor_dir / "references"
    for path in sorted(references_dir.glob("*.yml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        entries: dict[str, ReferenceEntry] = {}
        for key, value in (raw.get("entries") or {}).items():
            value = value or {}
            entries[key] = ReferenceEntry(
                key=key,
                title=value.get("title"),
                url=value.get("url"),
                description=value.get("description"),
                issuer=value.get("issuer"),
            )
        frameworks[path.stem] = ReferenceFramework(
            name=path.stem,
            title=raw.get("title"),
            issuer=raw.get("issuer"),
            url=raw.get("source_url"),
            entries=entries,
        )
    return frameworks


def _resolve_references(
    metadata: dict[str, object], reference_frameworks: dict[str, ReferenceFramework]
) -> list[ExternalRef]:
    refs: list[ExternalRef] = []
    for meta_key, value in metadata.items():
        if not meta_key.endswith(_REFERENCES_SUFFIX) or not isinstance(value, list):
            continue
        dataset_name = meta_key[: -len(_REFERENCES_SUFFIX)]
        dataset = reference_frameworks.get(dataset_name)
        entries = dataset.entries if dataset is not None else {}
        for raw_key in value:
            key = str(raw_key)
            entry = entries.get(key)
            refs.append(
                ExternalRef(
                    framework=dataset_name,
                    key=key,
                    title=entry.title if entry else None,
                    url=entry.url if entry else None,
                    issuer=entry.issuer if entry else None,
                )
            )
    return refs


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v) for v in value]


def load_framework(vendor_dir: Path | None = None) -> Framework:
    vd = vendor_dir if vendor_dir is not None else _default_vendor_dir()
    verify(vd)

    config = yaml.safe_load((vd / "_config.yml").read_text(encoding="utf-8")) or {}
    version = str(config.get("version", ""))
    release_date = config.get("release-date")
    release_date_str = str(release_date) if release_date is not None else None

    type_labels: dict[str, str] = {}
    type_labels.update(config.get("risk_classification") or {})
    type_labels.update(config.get("mitigation_classification") or {})

    reference_frameworks = _load_reference_frameworks(vd)

    # Pass 1: parse every risk/mitigation file and index short_id -> public AIR id,
    # so pass 2 can resolve every cross-reference list regardless of file order.
    risk_posts: list[tuple[str, frontmatter.Post]] = []
    for path in sorted((vd / "risks").glob("*.md")):
        risk_posts.append((path.name, frontmatter.load(path)))
    control_posts: list[tuple[str, frontmatter.Post]] = []
    for path in sorted((vd / "mitigations").glob("*.md")):
        control_posts.append((path.name, frontmatter.load(path)))

    risk_short_to_id: dict[str, str] = {}
    for _filename, post in risk_posts:
        sequence = int(post.metadata["sequence"])
        risk_type: RiskType = post.metadata["type"]
        risk_short_to_id[f"ri-{sequence}"] = f"AIR-{risk_type}-{sequence:03d}"

    control_short_to_id: dict[str, str] = {}
    for _filename, post in control_posts:
        sequence = int(post.metadata["sequence"])
        control_type: ControlType = post.metadata["type"]
        control_short_to_id[f"mi-{sequence}"] = f"AIR-{control_type}-{sequence:03d}"

    # Pass 2: build the typed models, resolving cross-references via the maps above.
    risks: dict[str, Risk] = {}
    for filename, post in risk_posts:
        sequence = int(post.metadata["sequence"])
        risk_type = post.metadata["type"]
        short_id = f"ri-{sequence}"
        air_id = risk_short_to_id[short_id]
        summary, sections = _summary_and_sections(post.content)
        related = [
            risk_short_to_id[s] for s in _as_str_list(post.metadata.get("related_risks")) if s in risk_short_to_id
        ]
        risks[air_id] = Risk(
            id=air_id,
            short_id=short_id,
            sequence=sequence,
            type=risk_type,
            type_label=type_labels.get(risk_type, risk_type),
            title=str(post.metadata["title"]),
            status=str(post.metadata["doc-status"]),
            summary=summary,
            sections=sections,
            related_risks=related,
            mitigated_by=[],  # filled below by inverting `mitigates`
            references=_resolve_references(post.metadata, reference_frameworks),
            source_path=f"docs/_risks/{filename}",
            citation_uri=f"aigf://risk/{air_id}",
        )

    controls: dict[str, Control] = {}
    for filename, post in control_posts:
        sequence = int(post.metadata["sequence"])
        control_type = post.metadata["type"]
        short_id = f"mi-{sequence}"
        air_id = control_short_to_id[short_id]
        summary, sections = _summary_and_sections(post.content)
        mitigates = [
            risk_short_to_id[s] for s in _as_str_list(post.metadata.get("mitigates")) if s in risk_short_to_id
        ]
        related = [
            control_short_to_id[s]
            for s in _as_str_list(post.metadata.get("related_mitigations"))
            if s in control_short_to_id
        ]
        controls[air_id] = Control(
            id=air_id,
            short_id=short_id,
            sequence=sequence,
            type=control_type,
            type_label=type_labels.get(control_type, control_type),
            title=str(post.metadata["title"]),
            status=str(post.metadata["doc-status"]),
            summary=summary,
            sections=sections,
            mitigates=mitigates,
            related_controls=related,
            references=_resolve_references(post.metadata, reference_frameworks),
            source_path=f"docs/_mitigations/{filename}",
            citation_uri=f"aigf://control/{air_id}",
        )
        for risk_id in mitigates:
            if risk_id in risks:
                risks[risk_id].mitigated_by.append(air_id)

    return Framework(
        version=version,
        release_date=release_date_str,
        upstream_commit=_read_upstream_commit(vd),
        risks=risks,
        controls=controls,
        references=reference_frameworks,
        type_labels=type_labels,
    )


def _read_upstream_commit(vendor_dir: Path) -> str | None:
    from finos_mcp.core import SourceManifest

    manifest = SourceManifest.load(vendor_dir)
    return manifest.commit_sha


def framework_documents(fw: Framework) -> tuple[list[Document], list[Document]]:
    """Return (risk_documents, control_documents) for a generic search/resolve Catalog."""
    risk_docs: list[Document] = []
    for risk in fw.risks.values():
        stem = Path(risk.source_path).stem
        risk_docs.append(
            Document(
                id=risk.id,
                title=risk.title,
                aliases=[risk.short_id, str(risk.sequence), stem],
                kind="risk",
                body=f"{risk.summary}\n\n{_full_body(risk.sections)}",
                sections=risk.sections,
                meta={"type": risk.type, "status": risk.status},
            )
        )

    control_docs: list[Document] = []
    for control in fw.controls.values():
        stem = Path(control.source_path).stem
        control_docs.append(
            Document(
                id=control.id,
                title=control.title,
                aliases=[control.short_id, str(control.sequence), stem],
                kind="control",
                body=f"{control.summary}\n\n{_full_body(control.sections)}",
                sections=control.sections,
                meta={"type": control.type, "status": control.status},
            )
        )

    return risk_docs, control_docs


def _full_body(sections: list[Section]) -> str:
    parts: list[str] = []
    for section in sections:
        if section.heading:
            parts.append(f"## {section.heading}\n{section.body}")
        else:
            parts.append(section.body)
    return "\n\n".join(p for p in parts if p.strip())
