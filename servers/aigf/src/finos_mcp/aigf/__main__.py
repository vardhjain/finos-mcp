"""Console entry point: ``finos-mcp-aigf [--transport stdio|streamable-http]``."""

from __future__ import annotations

import argparse
import sys

from .server import create_server


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="finos-mcp-aigf", description=__doc__)
    ap.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)
    server = create_server()
    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main(sys.argv[1:])
