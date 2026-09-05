"""Generate docs/tools.md from each server's live tool, resource and prompt listings.

uv run python -m finos_mcp_evals.toolref --out docs/tools.md
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
from pathlib import Path
from typing import Any

from mcp.client import Client

SERVERS = ("aigf", "cdm", "fdc3")


def _schema_summary(schema: dict[str, Any] | None) -> str:
    if not schema:
        return "-"
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    parts = []
    for name, spec in props.items():
        t = spec.get("type") or ("enum" if "enum" in spec else spec.get("$ref", "object"))
        if isinstance(t, list):
            t = "/".join(str(x) for x in t)
        if "anyOf" in spec:
            t = "/".join(str(o.get("type", "?")) for o in spec["anyOf"])
        parts.append(f"`{name}`{'*' if name in required else ''}: {t}")
    return ", ".join(parts) or "-"


async def describe(server: str) -> str:
    module = importlib.import_module(f"finos_mcp.{server}.server")
    lines = [f"## finos-mcp-{server}", ""]
    async with Client(module.create_server(), raise_exceptions=True) as client:
        info = (await client.call_tool("server_info", {})).structured_content or {}
        lines.append(
            f"{info.get('standard')} {info.get('standard_version') or ''} — upstream "
            f"`{info.get('upstream_repo')}@{info.get('upstream_ref')}` "
            f"({(info.get('upstream_commit') or '')[:12]}). "
            f"Exposes: {', '.join(f'{k}={v}' for k, v in sorted(info.get('counts', {}).items()))}."
        )
        lines += [
            "",
            "### Tools",
            "",
            "| Tool | Arguments (`*` required) | Description |",
            "|---|---|---|",
        ]
        for t in sorted((await client.list_tools()).tools, key=lambda t: t.name):
            desc = " ".join((t.description or "").split())
            lines.append(f"| `{t.name}` | {_schema_summary(t.input_schema)} | {desc} |")
        templates = (await client.list_resource_templates()).resource_templates
        resources = (await client.list_resources()).resources
        if templates or resources:
            lines += ["", "### Resources", "", "| URI | Title | MIME |", "|---|---|---|"]
            for r in templates:
                lines.append(f"| `{r.uri_template}` | {r.title or r.name} | {r.mime_type or ''} |")
            for res in resources:
                lines.append(f"| `{res.uri}` | {res.title or res.name} | {res.mime_type or ''} |")
        prompts = (await client.list_prompts()).prompts
        if prompts:
            lines += ["", "### Prompts", ""]
            for p in prompts:
                args = ", ".join(f"`{a.name}`" for a in (p.arguments or []))
                lines.append(f"- `{p.name}`({args}): {p.description or ''}")
    lines.append("")
    return "\n".join(lines)


async def build() -> str:
    head = [
        "# Tool reference",
        "",
        "Generated from the live servers by `uv run python -m finos_mcp_evals.toolref`. "
        "Every tool is read-only, returns typed `structuredContent` described by its "
        "`outputSchema`, and raises structured errors (`not_found`, `ambiguous_id`, "
        "`invalid_input`, ...) the calling agent can act on.",
        "",
    ]
    sections = [await describe(s) for s in SERVERS]
    return "\n".join(head + sections)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("docs/tools.md"))
    ap.add_argument("--check", action="store_true", help="fail if the file would change")
    args = ap.parse_args(argv)
    text = asyncio.run(build())
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
        if current != text:
            raise SystemExit(f"{args.out} is stale; regenerate it")
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
