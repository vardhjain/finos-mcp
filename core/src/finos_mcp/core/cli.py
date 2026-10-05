"""The command line every finos-mcp server shares.

``finos-mcp-<name> [--transport stdio|streamable-http] [--host H] [--port P]
[--allowed-host HOST ...] [--allowed-origin ORIGIN ...]``

Over HTTP the MCP SDK checks the ``Host`` and ``Origin`` headers of each request (its
protection against DNS rebinding) only when the server is bound to a loopback address. Bound
to anything else, such as ``0.0.0.0`` in a container, it checks nothing unless it is told
which hosts are legitimate. ``--allowed-host`` and ``--allowed-origin`` (or the
``FINOS_MCP_ALLOWED_HOSTS`` / ``FINOS_MCP_ALLOWED_ORIGINS`` environment variables, comma
separated) do that, so a container published on a workstation port can refuse requests a
browser page makes with another site's ``Host`` or ``Origin``.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
ENV_ALLOWED_HOSTS = "FINOS_MCP_ALLOWED_HOSTS"
ENV_ALLOWED_ORIGINS = "FINOS_MCP_ALLOWED_ORIGINS"


def _from_env(env: Mapping[str, str], name: str) -> list[str]:
    return [item.strip() for item in env.get(name, "").split(",") if item.strip()]


def build_parser(prog: str, default_port: int) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog=prog, description=f"{prog}: a read-only MCP server. Speaks stdio by default."
    )
    ap.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    ap.add_argument("--host", default="127.0.0.1", help="address to bind for streamable-http")
    ap.add_argument("--port", type=int, default=default_port)
    ap.add_argument(
        "--allowed-host",
        action="append",
        default=[],
        metavar="HOST[:PORT]",
        help="a Host header value to accept over HTTP, e.g. mcp.example.com or "
        f"localhost:* (repeatable; also {ENV_ALLOWED_HOSTS}, comma separated)",
    )
    ap.add_argument(
        "--allowed-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help="an Origin header value to accept over HTTP, e.g. https://app.example.com "
        f"(repeatable; also {ENV_ALLOWED_ORIGINS}, comma separated)",
    )
    return ap


def transport_security(
    host: str, allowed_hosts: list[str], allowed_origins: list[str]
) -> tuple[TransportSecuritySettings | None, str | None]:
    """The settings to hand the SDK, and a warning to print, for one HTTP configuration.

    With an allow-list, header checking is switched on for it whatever the bind address.
    Without one, the SDK's own default applies (checking on a loopback bind only), and a
    non-loopback bind gets a warning.
    """
    if allowed_hosts or allowed_origins:
        if not allowed_hosts:
            return None, (
                "finos-mcp: --allowed-origin was given without --allowed-host. The Host "
                "header is checked first, so name the hosts as well; nothing is being checked."
            )
        return (
            TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=allowed_hosts,
                allowed_origins=allowed_origins,
            ),
            None,
        )
    if host not in LOOPBACK_HOSTS:
        return None, (
            f"finos-mcp: listening on {host}, which is reachable from other machines. The "
            "server has no authentication and is not checking Host or Origin headers on this "
            "address. Pass --allowed-host (and --allowed-origin), and put an authenticating "
            "reverse proxy in front of it."
        )
    return None, None


def serve(
    create_server: Callable[[], MCPServer[Any]],
    *,
    prog: str,
    default_port: int,
    argv: list[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    args = build_parser(prog, default_port).parse_args(argv)
    server = create_server()
    if args.transport == "stdio":
        server.run(transport="stdio")
        return
    environ = os.environ if env is None else env
    hosts = [*args.allowed_host, *_from_env(environ, ENV_ALLOWED_HOSTS)]
    origins = [*args.allowed_origin, *_from_env(environ, ENV_ALLOWED_ORIGINS)]
    settings, warning = transport_security(args.host, hosts, origins)
    if warning:
        print(warning, file=sys.stderr)
    if settings is None:
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            transport_security=settings,
        )
