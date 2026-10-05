"""Console entry point: ``finos-mcp-cdm [--transport stdio|streamable-http]``."""

from __future__ import annotations

import argparse
import sys

from .server import create_server

_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="finos-mcp-cdm", description=__doc__)
    ap.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8001)
    args = ap.parse_args(argv)
    server = create_server()
    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        if args.host not in _LOOPBACK:
            # The SDK validates Host and Origin headers only for a loopback bind.
            print(
                f"finos-mcp: listening on {args.host}, which is reachable from other machines. "
                "The server has no authentication and does not check Host or Origin headers "
                "on this address: put an authenticating reverse proxy in front of it.",
                file=sys.stderr,
            )
        server.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main(sys.argv[1:])
