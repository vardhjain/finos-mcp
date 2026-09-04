"""Regex-based extraction of a few facts from CDM ``.rosetta`` source files.

The CDM JSON Schema distribution (Maven Central) has no equivalent of:

* the 35 ``Qualify_*`` event-qualification functions and their bodies, or
* the ``[rootType]`` / ``choice`` annotations that mark root types and choice
  (discriminated-union) types.

Those live only in the ``.rosetta`` DSL source published on GitHub. This module
parses just enough of that DSL -- with regexes, not a real Rosetta parser -- to
recover the three checked-in vendor files:

* ``_vendor/qualify.json``      (``extract_qualify``)
* ``_vendor/root_types.json``   (``extract_root_types``)
* ``_vendor/choice_types.json`` (``extract_choice_types``)

Used by ``sync_upstream.py``; stdlib only so it can be imported the same way.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_FUNC_START = re.compile(r"^func (Qualify_\w+):", re.MULTILINE)
_DOCSTRING = re.compile(r'<"(.*?)">', re.DOTALL)
_INPUTS_BLOCK = re.compile(r"\binputs:\s*\n(.*?)\n\s*output:", re.DOTALL)
_OUTPUT_BLOCK = re.compile(r"\boutput:\s*\n(.*?)(?:\n\s*\n|\Z)", re.DOTALL)
_CONDITION_MARKER = re.compile(r"(set is_event:|condition\s+\w+:)", re.MULTILINE)

_NAMESPACE_LINE = re.compile(r"^namespace\s+([\w.]+)", re.MULTILINE)
_TYPE_DECL = re.compile(
    r"^type\s+(\w+)(?:\s+extends\s+(\w+))?\s*:(?:[ \t]*<\"(.*?)\">)?[ \t]*\n"
    r"((?:[ \t]*\[[^\]]*\]\s*\n)*)",
    re.MULTILINE,
)
_CHOICE_DECL = re.compile(
    r'^choice\s+(\w+)\s*:(?:[ \t]*<"(.*?)">)?[ \t]*\n((?:.*\n)*?)(?=\n\S|\Z)',
    re.MULTILINE,
)
_ALTERNATIVE_LINE = re.compile(r"^[ \t]+([A-Z]\w*)\b")


def _namespace_of(text: str) -> str:
    match = _NAMESPACE_LINE.search(text)
    return match.group(1) if match else ""


def extract_qualify(rosetta_dir: Path) -> list[dict[str, Any]]:
    """Parse ``event-qualification-func.rosetta`` into a list of function facts.

    Each entry has: ``name``, ``has_business_event_annotation``, ``docstring``,
    ``inputs`` (raw ``name Type (card)`` strings), ``output`` (same shape), and
    ``condition_text`` (the verbatim, trimmed body from ``set is_event:`` --
    or a fallback ``condition <Name>:`` block -- to the end of the function).
    """
    path = rosetta_dir / "event-qualification-func.rosetta"
    text = path.read_text(encoding="utf-8")

    starts = list(_FUNC_START.finditer(text))
    functions: list[dict[str, Any]] = []
    for i, m in enumerate(starts):
        block_start = m.start()
        block_end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        block = text[block_start:block_end]
        name = m.group(1)

        header_end = block.find("\n")
        header_rest = block[m.end() - block_start : header_end if header_end != -1 else None]
        doc_match = _DOCSTRING.search(header_rest)
        docstring = doc_match.group(1).strip() if doc_match else None

        has_annotation = "[qualification BusinessEvent]" in block

        inputs: list[str] = []
        inputs_match = _INPUTS_BLOCK.search(block)
        if inputs_match:
            inputs = [line.strip() for line in inputs_match.group(1).splitlines() if line.strip()]

        output: str | None = None
        output_match = _OUTPUT_BLOCK.search(block)
        if output_match:
            lines = [line.strip() for line in output_match.group(1).splitlines() if line.strip()]
            output = lines[0] if lines else None

        cond_match = _CONDITION_MARKER.search(block)
        condition_text = block[cond_match.start() :].strip() if cond_match else ""

        functions.append(
            {
                "name": name,
                "has_business_event_annotation": has_annotation,
                "docstring": docstring,
                "inputs": inputs,
                "output": output,
                "condition_text": condition_text,
            }
        )
    return functions


def extract_root_types(rosetta_dir: Path) -> list[dict[str, Any]]:
    """Scan every ``.rosetta`` file for ``type <Name>[ extends <Parent>]:``
    declarations annotated ``[rootType]`` directly below the declaration line.

    Returns a list of ``{"name", "namespace", "extends", "source_file"}``.
    """
    root_types: list[dict[str, Any]] = []
    for path in sorted(rosetta_dir.glob("*.rosetta")):
        text = path.read_text(encoding="utf-8")
        namespace = _namespace_of(text)
        for m in _TYPE_DECL.finditer(text):
            annotations = m.group(4) or ""
            if "[rootType]" not in annotations:
                continue
            root_types.append(
                {
                    "name": m.group(1),
                    "namespace": namespace,
                    "extends": m.group(2),
                    "source_file": path.name,
                }
            )
    return root_types


def extract_choice_types(rosetta_dir: Path) -> list[dict[str, Any]]:
    """Scan every ``.rosetta`` file for ``choice <Name>:`` declarations.

    Returns a list of ``{"name", "namespace", "alternatives", "source_file"}``
    where ``alternatives`` is a best-effort list of the alternative type names
    listed under the choice (blank once the block cannot be parsed cleanly).
    """
    choices: list[dict[str, Any]] = []
    for path in sorted(rosetta_dir.glob("*.rosetta")):
        text = path.read_text(encoding="utf-8")
        namespace = _namespace_of(text)
        for m in _CHOICE_DECL.finditer(text):
            body = m.group(3)
            alternatives: list[str] = []
            for line in body.splitlines():
                if not line.strip():
                    continue
                if line.lstrip().startswith("["):
                    continue
                alt_match = _ALTERNATIVE_LINE.match(line)
                if alt_match:
                    alternatives.append(alt_match.group(1))
            choices.append(
                {
                    "name": m.group(1),
                    "namespace": namespace,
                    "alternatives": alternatives,
                    "source_file": path.name,
                }
            )
    return choices
