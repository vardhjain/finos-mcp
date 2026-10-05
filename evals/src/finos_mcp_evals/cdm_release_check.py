"""Report CDM releases newer than the vendored ones.

Usage: ``uv run python -m finos_mcp_evals.cdm_release_check [--out report.md]``

The weekly vendor check re-syncs the CDM versions this repository already vendors, so on
its own it never notices a new CDM release. This compares the vendored schema versions with
the ``cdm-json-schema`` artifacts published on Maven Central and reports, for each vendored
release line (the major version), the newest stable release in that line, plus any stable
release in a newer major line.

It only reports. A CDM bump is deliberately not automated: the primary version is a constant
in ``finos_mcp.cdm.registry``, and tests pin the schema count and known upstream defects, so a
bump is a reviewed change (see CONTRIBUTING.md).

Exit status is 0 whether or not something newer exists; ``newer=true|false`` is written to
``$GITHUB_OUTPUT`` when that variable is set. A network failure exits non-zero.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.request
from pathlib import Path

METADATA_URL = "https://repo1.maven.org/maven2/org/finos/cdm/cdm-json-schema/maven-metadata.xml"
_STABLE = re.compile(r"^\d+\.\d+\.\d+$")
_BUNDLE = re.compile(r"^cdm-json-schema-(\d+\.\d+\.\d+)\.json$")

Version = tuple[int, int, int]


def parse(version: str) -> Version:
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch


def stable_versions(metadata_xml: str) -> list[str]:
    """Every stable ``x.y.z`` version in a maven-metadata.xml, oldest first. Pre-releases
    such as ``8.0.0-dev.8`` are ignored."""
    found = re.findall(r"<version>([^<]+)</version>", metadata_xml)
    return sorted({v for v in found if _STABLE.match(v)}, key=parse)


def vendored_versions(schemas_dir: Path) -> list[str]:
    """The CDM versions whose schema bundles are vendored, oldest first."""
    names = (m.group(1) for p in schemas_dir.glob("*.json") if (m := _BUNDLE.match(p.name)))
    return sorted(names, key=parse)


def newer_releases(vendored: list[str], published: list[str]) -> list[tuple[str, str]]:
    """``(what is vendored, newer release)`` pairs.

    One pair per vendored version that is behind the newest stable release in its own major
    line, and one pair for the newest stable release of each major line above every vendored
    one, described as vendored ``"none"``.
    """
    out: list[tuple[str, str]] = []
    for have in vendored:
        line = [v for v in published if parse(v)[0] == parse(have)[0]]
        if line and parse(line[-1]) > parse(have):
            out.append((have, line[-1]))
    top_major = max((parse(v)[0] for v in vendored), default=-1)
    for major in sorted({parse(v)[0] for v in published if parse(v)[0] > top_major}):
        out.append(("none", [v for v in published if parse(v)[0] == major][-1]))
    return out


def report(vendored: list[str], newer: list[tuple[str, str]]) -> str:
    lines = [f"Vendored CDM schema versions: {', '.join(vendored) or 'none'}.", ""]
    if not newer:
        lines.append("No newer stable CDM release is published.")
        return "\n".join(lines) + "\n"
    lines.append("Newer stable releases on Maven Central:")
    lines.append("")
    for have, latest in newer:
        if have == "none":
            lines.append(f"- **{latest}** starts a release line that is not vendored.")
        else:
            lines.append(f"- **{latest}** is newer than the vendored {have}.")
    lines += [
        "",
        "To bump: run `servers/cdm/scripts/sync_upstream.py --version <7.x> --legacy-version "
        "<6.x>`, update `PRIMARY_VERSION` in `servers/cdm/src/finos_mcp/cdm/registry.py`, the "
        "versions in `.github/workflows/vendor-check.yml`, and the version strings and schema "
        "count the CDM tests and golden cases pin. Then check whether any finding in "
        "`docs/upstream-findings.md` has been fixed upstream.",
    ]
    return "\n".join(lines) + "\n"


def _default_schemas_dir() -> Path:
    import finos_mcp.cdm

    return Path(finos_mcp.cdm.__file__ or "").parent / "_vendor" / "schemas"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, help="also write the report to this file")
    args = ap.parse_args(argv)

    with urllib.request.urlopen(METADATA_URL, timeout=30) as response:
        published = stable_versions(response.read().decode("utf-8"))
    vendored = vendored_versions(_default_schemas_dir())
    newer = newer_releases(vendored, published)
    text = report(vendored, newer)
    print(text, end="")
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"newer={'true' if newer else 'false'}\n")
            fh.write(f"latest={' '.join(latest for _, latest in newer)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
