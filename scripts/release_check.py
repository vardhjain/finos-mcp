"""Preflight checks for FINOS MCP version alignment and release archives.

Run from anywhere: python scripts/release_check.py --tag v0.3.0 [--dist dist].
Never uploads packages, creates tags, or calls external services.
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import tomllib
import zipfile
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = (
    ("pyproject.toml", "finos-mcp-workspace"),
    ("core/pyproject.toml", "finos-mcp-core"),
    ("servers/aigf/pyproject.toml", "finos-mcp-aigf"),
    ("servers/cdm/pyproject.toml", "finos-mcp-cdm"),
    ("servers/fdc3/pyproject.toml", "finos-mcp-fdc3"),
    ("evals/pyproject.toml", "finos-mcp-evals"),
)
PUBLISHED = ("core", "aigf", "cdm", "fdc3")


def validate_versions(root: Path = ROOT, tag: str | None = None) -> str:
    manifests = {
        project: tomllib.loads((root / path).read_text(encoding="utf-8"))["project"]
        for path, project in PROJECTS
    }
    version = manifests["finos-mcp-workspace"]["version"]
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"tag {tag!r} does not match package version v{version}")
    for project, data in manifests.items():
        if data["name"] != project or data["version"] != version:
            raise ValueError(f"{project} metadata differs from workspace version {version}")
    for project in ("finos-mcp-aigf", "finos-mcp-cdm", "finos-mcp-fdc3"):
        deps = manifests[project]["dependencies"]
        if not any(dep.startswith(f"finos-mcp-core>={version}") for dep in deps):
            raise ValueError(f"{project} must require finos-mcp-core>={version}")
    semantic = manifests["finos-mcp-aigf"].get("optional-dependencies", {}).get("semantic", [])
    if not any(dep.startswith(f"finos-mcp-core[semantic]>={version}") for dep in semantic):
        raise ValueError("AIGF's semantic extra must require the matching core version")
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    versions = {p["name"]: p["version"] for p in lock["package"] if p["name"] in manifests}
    if set(versions) != set(manifests):
        raise ValueError(f"locked workspace packages differ: {sorted(versions)}")
    for project, locked in versions.items():
        if locked != version:
            raise ValueError(f"uv.lock has {project}=={locked}, expected {version}")
    print(f"PASS: six manifests and uv.lock match v{version}")
    return version


def validate_artifacts(path: Path, version: str) -> None:
    if not path.is_dir():
        raise ValueError(f"release artifact directory does not exist: {path}")
    expected: set[str] = set()
    for component in PUBLISHED:
        stem = f"finos_mcp_{component}-{version}"
        wheels = list(path.glob(f"{stem}-*.whl"))
        if len(wheels) != 1:
            raise ValueError(f"expected exactly one wheel for {stem}, found {len(wheels)}")
        wheel = wheels[0]
        archive = path / f"{stem}.tar.gz"
        if not archive.is_file():
            raise ValueError(f"missing source distribution: {archive.name}")
        expected.update((wheel.name, archive.name))
        with zipfile.ZipFile(wheel) as zf:
            metadata_paths = [n for n in zf.namelist() if n.endswith(".dist-info/METADATA")]
            if len(metadata_paths) != 1:
                raise ValueError(f"{wheel.name}: missing/duplicate wheel metadata")
            message = Parser().parsestr(zf.read(metadata_paths[0]).decode("utf-8"))
            if message["Name"].lower().replace("_", "-") != f"finos-mcp-{component}":
                raise ValueError(f"{wheel.name}: wrong Name in METADATA")
            if message["Version"] != version:
                raise ValueError(f"{wheel.name}: wrong Version in METADATA")
            if component != "core" and not any(
                f"finos-mcp-core>={version}" in dep.replace(" ", "")
                for dep in message.get_all("Requires-Dist", [])
            ):
                raise ValueError(f"{wheel.name}: missing minimum core dependency")
            # All published wheels must carry the exact offline provenance records.
            if component != "core" and not any(n.endswith("/_vendor/SOURCE.json") for n in zf.namelist()):
                raise ValueError(f"{wheel.name}: missing vendored content provenance")
        with tarfile.open(archive, "r:gz") as tf:
            if not any(n.endswith("pyproject.toml") for n in tf.getnames()):
                raise ValueError(f"{archive.name}: missing project metadata")
    if {p.name for p in path.iterdir() if p.is_file()} != expected:
        raise ValueError("dist/ includes unexpected or incomplete release artifacts")
    print(f"PASS: {len(expected)} valid release artifacts (wheel + sdist per package)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="Expected git release tag, for example v0.3.0")
    parser.add_argument("--dist", type=Path, help="Optional built artifact directory to validate")
    args = parser.parse_args()
    try:
        version = validate_versions(tag=args.tag)
        if args.dist is not None:
            validate_artifacts(args.dist, version)
    except (ValueError, OSError, KeyError, tomllib.TOMLDecodeError) as exc:
        print(f"RELEASE CHECK FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
