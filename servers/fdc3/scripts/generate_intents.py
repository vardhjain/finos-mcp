"""Parse vendored FDC3 intent reference docs into ``_vendor/intents.json``.

The FDC3 intent <-> context mapping is not published anywhere machine-readable
(see PLAN.md 1.3): it only exists as ``## Possible Contexts`` bullet lists (and,
for a couple of intents, a "SHOULD return context as a result:" sub-list, or a
free-form ``## Output`` section) inside the markdown files vendored by
``sync_upstream.py`` at ``_vendor/intents/*.md``. This module parses those docs
plus the vendored context schemas (to map context titles/links to ``fdc3.*``
``type`` consts) and the vendored ``Intents.ts`` (the authoritative list of
standard intent names) into one deterministic ``intents.json``.

Usage::

    uv run python servers/fdc3/scripts/generate_intents.py

``generate(vendor_dir)`` is the importable entry point used both by this
script's ``main()`` and by the drift test in ``servers/fdc3/tests``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# Upstream directory the vendored `_vendor/intents/*.md` files were downloaded
# from (see sync_upstream.py); recorded here so `doc_path` in intents.json
# points at the real upstream location even though the vendored copy is flat.
UPSTREAM_INTENTS_DIR = "website/docs/intents/ref"

_BULLET_LINK_RE = re.compile(r"^[-*]\s*\[([^\]]+)\]\(([^)]+)\)", re.MULTILINE)
_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)\s*$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_RESULT_MARKER_RE = re.compile(r"(?i)SHOULD\s+return\s+context\s+as\s+a\s+result:?")
_RESULT_HEADING_RE = re.compile(r"(?i)^(result type|output|returns?)$")
_SINCE_RE = re.compile(r"(?i)\b(?:since|added in)\s+(?:fdc3\s+)?v?(\d+\.\d+(?:\.\d+)?)")
_ADMONITION_RE = re.compile(r"^:::\s*(caution|warning|danger|note|info|tip)\b", re.IGNORECASE)


def _normalize(text: str) -> str:
    """Case-fold and drop non-alphanumerics so 'File Attachment' == 'fileAttachment'."""
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def _find_type_const(node: Any) -> str | None:
    """Depth-first search for the first `properties.type.const` in a schema tree."""
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict) and "type" in props:
            type_prop = props["type"]
            if isinstance(type_prop, dict) and isinstance(type_prop.get("const"), str):
                return type_prop["const"]
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


class _ContextEntry:
    __slots__ = ("title", "type")

    def __init__(self, type_const: str, title: str) -> None:
        self.type = type_const
        self.title = title


def _load_context_index(schemas_dir: Path) -> tuple[dict[str, str], list[_ContextEntry]]:
    """Build a lookup from normalized title/filename/type -> `fdc3.*` type const.

    `context.schema.json` (the base type all others `$ref`) has no `type` const
    of its own and is skipped, matching the registry's own convention.
    """
    table: dict[str, str] = {}
    entries: list[_ContextEntry] = []
    for path in sorted(schemas_dir.glob("*.schema.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        type_const = _find_type_const(data)
        if type_const is None:
            continue
        title = str(data.get("title") or path.stem)
        filename_stem = path.name.removesuffix(".schema.json")
        entries.append(_ContextEntry(type_const, title))
        for key in (title, filename_stem, type_const, type_const.split(".", 1)[-1]):
            table.setdefault(_normalize(key), type_const)
    return table, entries


def _load_standard_intent_names(intents_ts: Path) -> set[str]:
    """Extract the `StandardIntent` string-literal union from the vendored Intents.ts."""
    if not intents_ts.exists():
        return set()
    text = intents_ts.read_text(encoding="utf-8")
    match = re.search(r"export type StandardIntent\s*=\s*(.*?);", text, re.DOTALL)
    if not match:
        return set()
    return set(re.findall(r"'([^']+)'", match.group(1)))


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    frontmatter: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        frontmatter[key.strip()] = value.strip().strip('"').strip("'")
    return frontmatter, text[match.end() :]


def _sections(body: str) -> list[tuple[int, str, str]]:
    """Split `body` into (level, heading, section_text) for each heading line."""
    headings = list(_HEADING_RE.finditer(body))
    out: list[tuple[int, str, str]] = []
    for i, heading_match in enumerate(headings):
        level = len(heading_match.group(1))
        heading = heading_match.group(2).strip()
        start = heading_match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        out.append((level, heading, body[start:end]))
    return out


def _extract_links(text: str) -> list[tuple[str, str]]:
    return [(m.group(1).strip(), m.group(2).strip()) for m in _BULLET_LINK_RE.finditer(text)]


def _resolve_type(link_text: str, link_target: str, table: dict[str, str]) -> str | None:
    for candidate in (link_text, link_target.rsplit("/", 1)[-1]):
        resolved = table.get(_normalize(candidate))
        if resolved is not None:
            return resolved
    return None


def _parse_possible_contexts(
    section_body: str, table: dict[str, str]
) -> tuple[list[str], str | None]:
    """Split a `## Possible Contexts` section on the optional result marker.

    A couple of intents (e.g. CreateInteraction) embed the result type in the
    same section as a second bullet list introduced by
    "SHOULD return context as a result:".
    """
    marker = _RESULT_MARKER_RE.search(section_body)
    if marker:
        contexts_text, result_text = section_body[: marker.start()], section_body[marker.end() :]
    else:
        contexts_text, result_text = section_body, ""

    contexts: list[str] = []
    for text, target in _extract_links(contexts_text):
        resolved = _resolve_type(text, target, table)
        if resolved is not None and resolved not in contexts:
            contexts.append(resolved)

    result: str | None = None
    for text, target in _extract_links(result_text):
        resolved = _resolve_type(text, target, table)
        if resolved is not None:
            result = resolved
            break
    return contexts, result


def _find_result_from_heading(
    sections: list[tuple[int, str, str]], table: dict[str, str], entries: list[_ContextEntry]
) -> str | None:
    """Fall back to a `## Output` / `## Result Type` / `## Returns` section.

    Prefers a markdown link resolvable via `table`; otherwise looks for a
    known context title mentioned as a whole word in the prose (longest title
    first, so e.g. "ContactList" is preferred over a bare "Contact" match).
    """
    for _level, heading, body in sections:
        if not _RESULT_HEADING_RE.match(heading):
            continue
        for text, target in _extract_links(body):
            resolved = _resolve_type(text, target, table)
            if resolved is not None:
                return resolved
        for entry in sorted(entries, key=lambda e: -len(e.title)):
            if re.search(r"\b" + re.escape(entry.title) + r"\b", body):
                return entry.type
    return None


def _is_deprecated(body: str) -> bool:
    head = "\n".join(body.splitlines()[:15])
    if any(_ADMONITION_RE.match(line.strip()) for line in head.splitlines()):
        # Only ":::caution"/":::warning" (not e.g. ":::note") imply deprecation.
        for line in head.splitlines():
            m = _ADMONITION_RE.match(line.strip())
            if m and m.group(1).casefold() in {"caution", "warning"}:
                return True
    return "deprecated" in head.casefold()


_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def _clean_markdown(text: str) -> str:
    """Strip inline markdown (links, backticks) so descriptions read as plain prose."""
    text = _MD_LINK_RE.sub(r"\1", text)
    return text.replace("`", "")


def _first_paragraph(body: str) -> str:
    paragraph: list[str] = []
    started = False
    in_admonition = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(":::"):
            in_admonition = not in_admonition
            continue
        if in_admonition:
            continue
        if stripped.startswith("#"):
            continue
        if not stripped:
            if started:
                break
            continue
        started = True
        paragraph.append(stripped)
    return _clean_markdown(" ".join(paragraph).strip())


def _find_since(body: str) -> str | None:
    match = _SINCE_RE.search(body)
    return match.group(1) if match else None


def _parse_intent_doc(
    path: Path, table: dict[str, str], entries: list[_ContextEntry], standard_names: set[str]
) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    name = frontmatter.get("id") or path.stem
    title = frontmatter.get("title") or name
    sections = _sections(body)

    contexts: list[str] = []
    result: str | None = None
    for _level, heading, section_body in sections:
        if _normalize(heading) == _normalize("Possible Contexts"):
            contexts, result = _parse_possible_contexts(section_body, table)
            break
    if result is None:
        result = _find_result_from_heading(sections, table, entries)

    return {
        "name": name,
        "title": title,
        "contexts": sorted(contexts),
        "result": result,
        "deprecated": _is_deprecated(body),
        "standard": name in standard_names if standard_names else True,
        "since": _find_since(body),
        "doc_path": f"{UPSTREAM_INTENTS_DIR}/{path.name}",
        "description": _first_paragraph(body),
    }


def generate(vendor_dir: Path) -> dict[str, Any]:
    """Regenerate the intents table from vendored schemas, docs and Intents.ts."""
    schemas_dir = vendor_dir / "schemas" / "context"
    intents_dir = vendor_dir / "intents"
    table, entries = _load_context_index(schemas_dir)
    standard_names = _load_standard_intent_names(vendor_dir / "Intents.ts")

    records = [
        _parse_intent_doc(path, table, entries, standard_names)
        for path in sorted(intents_dir.glob("*.md"))
    ]
    records.sort(key=lambda r: str(r["name"]))

    doc_names = {r["name"] for r in records}
    missing_in_docs = sorted(standard_names - doc_names)
    extra_in_docs = sorted(doc_names - standard_names) if standard_names else []
    if missing_in_docs or extra_in_docs:
        sys.stderr.write(
            "generate_intents: drift between Intents.ts and doc filenames -- "
            f"missing_in_docs={missing_in_docs} docs_only={extra_in_docs}\n"
        )

    return {"intents": records, "count": len(records)}


def write_intents_json(vendor_dir: Path) -> dict[str, Any]:
    data = generate(vendor_dir)
    out_path = vendor_dir / "intents.json"
    out_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return data


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vendor-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src" / "finos_mcp" / "fdc3" / "_vendor",
        help="Vendor directory containing schemas/context, intents and Intents.ts",
    )
    args = parser.parse_args(argv)
    data = write_intents_json(args.vendor_dir)
    print(f"Wrote intents.json with {data['count']} intent(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
