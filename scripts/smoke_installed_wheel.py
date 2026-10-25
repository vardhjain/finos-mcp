"""Smoke-test a *built and installed* FINOS MCP wheel, not a workspace checkout.

Run from outside the source tree using the clean virtualenv interpreter:
  .release-wheel-venv/bin/python -I scripts/smoke_installed_wheel.py aigf 0.3.0
No network, paid inference, or source checkout is needed at runtime.
"""

from __future__ import annotations

import importlib
import sys
from importlib.metadata import version
from pathlib import Path


def run(component: str, expected_version: str) -> None:
    if component not in {"aigf", "cdm", "fdc3"}:
        raise ValueError(f"unknown server: {component}")
    env = Path(sys.prefix).resolve()
    if env == Path(sys.base_prefix).resolve():
        raise RuntimeError("Smoke test requires an isolated virtual environment")
    for project in ("core", component):
        name = f"finos-mcp-{project}"
        actual = version(name)
        if actual != expected_version:
            raise RuntimeError(f"{name}: installed {actual}, expected {expected_version}")

    from finos_mcp.core import verify

    module = importlib.import_module(f"finos_mcp.{component}")
    module_path = Path(module.__file__).resolve()
    if not module_path.is_relative_to(env):
        raise RuntimeError(f"{component}: loaded source outside the virtualenv: {module_path}")
    verify(module_path.parent / "_vendor")

    server_module = importlib.import_module(f"finos_mcp.{component}.server")
    server = server_module.create_server()
    if server is None:
        raise RuntimeError(f"{component}: failed to construct MCP server")
    print(f"PASS: installed {component} {expected_version}, vendored content and MCP factory")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: smoke_installed_wheel.py <aigf|cdm|fdc3> <version>")
    run(sys.argv[1], sys.argv[2])
