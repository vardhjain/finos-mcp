"""Console entry point: ``finos-mcp-fdc3 [--transport stdio|streamable-http]``.

The options, including the Host and Origin allow-lists for HTTP, are in
``finos_mcp.core.cli``.
"""

from __future__ import annotations

import sys

from finos_mcp.core.cli import serve

from .server import create_server


def main(argv: list[str] | None = None) -> None:
    serve(create_server, prog="finos-mcp-fdc3", default_port=8002, argv=argv)


if __name__ == "__main__":
    main(sys.argv[1:])
