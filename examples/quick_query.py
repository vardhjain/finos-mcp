"""Call one tool on one server through the in-memory MCP client and print the result.

    uv run python examples/quick_query.py aigf get_control '{"id": "mi-20"}'
    uv run python examples/quick_query.py cdm validate_object @path/to/document.json
    uv run python examples/quick_query.py fdc3 list_intents

A leading ``@`` reads the JSON arguments from a file; for ``validate_object`` /
``validate_context`` / ``explain_event`` a bare document file is wrapped as the
tool's object argument automatically.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path

from mcp.client import Client

WRAP = {"validate_object": "object", "validate_context": "context", "explain_event": "event"}


def _args(tool: str, raw: str | None) -> dict:
    if not raw:
        return {}
    if raw.startswith("@"):
        data = json.loads(Path(raw[1:]).read_text(encoding="utf-8"), strict=False)
        if tool in WRAP and (
            tool not in data or not isinstance(data, dict) or WRAP[tool] not in data
        ):
            return {WRAP[tool]: data}
        return data
    return json.loads(raw)


async def main(server: str, tool: str, raw: str | None) -> int:
    module = importlib.import_module(f"finos_mcp.{server}.server")
    async with Client(module.create_server(), raise_exceptions=True) as client:
        result = await client.call_tool(tool, _args(tool, raw))
        if result.is_error:
            print("ERROR:", result.content[0].text)
            return 1
        print(json.dumps(result.structured_content, indent=2)[:6000])
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(
        asyncio.run(main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
    )
