"""Server factory that installs the safety stack on every finos-mcp server.

Rules enforced here, not merely documented:

1. Every tool registered through `register_tool` carries read-only annotations,
   and a gate refuses to serve `tools/*` if any registered tool lacks them.
2. Serialised tool arguments above the policy cap are rejected before the tool
   runs, as a structured `input_too_large` result the model can act on.
3. Each (session, tool) pair is rate limited; exhaustion is a JSON-RPC error so
   the host, not the model, sees it.
4. Every request is audited; every tool call is timed.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from weakref import WeakKeyDictionary

from mcp.server.context import CallNext, HandlerResult, ServerMiddleware, ServerRequestContext
from mcp.server.mcpserver import MCPServer
from mcp.shared.exceptions import MCPError
from mcp.types import INTERNAL_ERROR, CallToolResult, TextContent, ToolAnnotations

from .audit import AuditLog, canonical_json
from .errors import RATE_LIMITED_CODE, ErrorEnvelope, rate_limited
from .metrics import Metrics
from .models import ServerInfo
from .policy import RateLimit, SafetyPolicy
from .ratelimit import RateLimiter

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


@dataclass(slots=True)
class Runtime:
    policy: SafetyPolicy
    limiter: RateLimiter
    audit: AuditLog
    metrics: Metrics
    tool_names: list[str]
    read_only_verified: bool = False
    #: Every tool the server actually serves, filled in when read-only is verified.
    known_tools: frozenset[str] = frozenset()


_RUNTIMES: WeakKeyDictionary[MCPServer[Any], Runtime] = WeakKeyDictionary()


#: The single key every call to a tool the server does not serve is accounted under.
UNKNOWN_TOOL = "<unknown>"
_MAX_TOOL_NAME = 128
#: Non-tool methods that return content and are therefore rate limited too.
_LIMITED_METHODS = frozenset({"resources/read", "prompts/get"})


def runtime_for(server: MCPServer[Any]) -> Runtime:
    return _RUNTIMES[server]


def _session_key(ctx: ServerRequestContext[Any, Any]) -> str:
    """Stable per-client key for rate limiting.

    Over HTTP the transport attaches the request; its ``Mcp-Session-Id`` header
    (or, failing that, the client address) identifies the caller. Over stdio one
    process serves exactly one client, so a single key is correct. The
    ``ServerSession`` object itself is rebuilt per message and is not a usable key.
    """
    request = ctx.request
    headers = getattr(request, "headers", None)
    if headers is not None:
        try:
            sid = headers.get("mcp-session-id")
        except (AttributeError, TypeError):
            sid = None
        if sid:
            return f"sid:{sid}"
        client = getattr(request, "client", None)
        host = getattr(client, "host", None)
        if host:
            return f"ip:{host}"
    return "local"


def _tool_name(ctx: ServerRequestContext[Any, Any]) -> str | None:
    if ctx.method != "tools/call" or not isinstance(ctx.params, Mapping):
        return None
    name = ctx.params.get("name")
    return name if isinstance(name, str) else None


def _arguments(ctx: ServerRequestContext[Any, Any]) -> Mapping[str, Any] | None:
    if not isinstance(ctx.params, Mapping):
        return None
    args = ctx.params.get("arguments")
    return args if isinstance(args, Mapping) else None


def _error_result(envelope: ErrorEnvelope) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=envelope.to_text())], is_error=True
    )


def _error_text(result: HandlerResult) -> str | None:
    """The text of a tools/call error result, or None if the result is not an error."""
    if isinstance(result, CallToolResult):
        if not result.is_error:
            return None
        return next((c.text for c in result.content if isinstance(c, TextContent)), "")
    if isinstance(result, dict) and result.get("isError"):
        # The lowlevel server hands middleware the serialised (camelCase) result.
        content = result.get("content") or []
        return next(
            (c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"),
            "",
        )
    return None


def _outcome(result: HandlerResult) -> tuple[str, bool]:
    """Classify a tools/call result as (outcome label, is_error)."""
    text = _error_text(result)
    if text is None:
        return "ok", False
    env = ErrorEnvelope.parse_text(text)
    return (f"tool_error:{env.code}" if env else "tool_error"), True


_ARGUMENT_ERROR = re.compile(r"\d+ validation errors? for \w+Arguments\n")
_ARGUMENT_FIELD = re.compile(r"^(\S[^\n]*)\n {2}(.+?) \[type=(\w+)", re.MULTILINE)


def _structure_argument_error(tool: str, result: HandlerResult) -> CallToolResult | None:
    """Turn the SDK's argument-validation failure into an `invalid_input` envelope.

    Arguments that do not fit a tool's input schema are rejected by the SDK before the tool
    runs, as free text from the validation library. Every other anticipated failure reaches
    the model as a structured envelope; this makes malformed arguments do the same. The
    rejected input value is not echoed back.
    """
    text = _error_text(result)
    if text is None or ErrorEnvelope.parse_text(text) is not None:
        return None
    header = _ARGUMENT_ERROR.search(text)
    if header is None:
        return None
    fields = [
        {"field": field, "problem": problem, "kind": kind}
        for field, problem, kind in _ARGUMENT_FIELD.findall(text[header.end() :])
    ]
    summary = "; ".join(f"{f['field']}: {f['problem']}" for f in fields)
    return _error_result(
        ErrorEnvelope(
            code="invalid_input",
            message=f"Invalid arguments for {tool}" + (f": {summary}" if summary else "."),
            hint="Check the argument names and types in the tool's input schema, then call again.",
            details={"fields": fields},
        )
    )


def _result_bytes(result: HandlerResult) -> int:
    if result is None:
        return 0
    try:
        payload = (
            result.model_dump_json(exclude_none=True)
            if hasattr(result, "model_dump_json")
            else json.dumps(result, default=str)
        )
    except (TypeError, ValueError):
        return -1
    return len(payload.encode("utf-8"))


def _make_middleware(server: MCPServer[Any], rt: Runtime) -> ServerMiddleware[Any]:
    async def safety(ctx: ServerRequestContext[Any, Any], call_next: CallNext) -> HandlerResult:
        tool = _tool_name(ctx)
        record: dict[str, Any] = {
            "method": ctx.method,
            "request_id": ctx.request_id,
            "session": _session_key(ctx),
        }
        if ctx.method.startswith("tools/") and not rt.read_only_verified:
            await _verify_read_only(server, rt)
        if tool is None:
            start = time.perf_counter()
            try:
                if ctx.method in _LIMITED_METHODS:
                    # Resources and prompts serve the same content as the tools, so they
                    # share the per-session budget idea: one bucket per method.
                    allowed, retry_after = rt.limiter.try_acquire(_session_key(ctx), ctx.method)
                    if not allowed:
                        raise rate_limited(ctx.method, retry_after)
                result = await call_next(ctx)
                record["outcome"] = "ok"
                return result
            except MCPError as exc:
                record["outcome"] = f"error:{exc.code}"
                raise
            except Exception:
                record["outcome"] = "internal"
                raise
            finally:
                record["duration_ms"] = round((time.perf_counter() - start) * 1000, 3)
                if ctx.request_id is not None:
                    rt.audit.write(record)

        # A name the server does not serve is caller-controlled text of any length. It must
        # not become a rate-limit bucket or a metrics entry of its own: a flood of invented
        # names would evict real buckets (resetting their limits) and grow the metrics
        # without bound. All such calls share one key, and the audit line gets a short form.
        shown = tool if len(tool) <= _MAX_TOOL_NAME else tool[:_MAX_TOOL_NAME] + "..."
        if tool not in rt.known_tools:
            tool = UNKNOWN_TOOL
        record["tool"] = shown
        args = _arguments(ctx)
        record.update(rt.audit.describe_args(args))
        start = time.perf_counter()
        outcome, is_error, limited = "internal", True, False
        try:
            cap = rt.policy.input_cap_for(tool)
            if record["args_bytes"] > cap:
                outcome, is_error = "input_too_large", True
                return _error_result(
                    ErrorEnvelope(
                        code="input_too_large",
                        message=f"Arguments are {record['args_bytes']} bytes; the cap for {shown} is {cap} bytes.",
                        hint="Send a smaller object, or narrow the request (fewer ids, smaller page_size).",
                        details={"limit_bytes": cap, "actual_bytes": record["args_bytes"]},
                    )
                )
            allowed, retry_after = rt.limiter.try_acquire(_session_key(ctx), tool)
            if not allowed:
                outcome, is_error, limited = "rate_limited", True, True
                raise rate_limited(tool, retry_after)
            result = await call_next(ctx)
            result = _structure_argument_error(shown, result) or result
            size = _result_bytes(result)
            record["result_bytes"] = size
            if size > rt.policy.max_output_bytes:
                outcome, is_error = "output_too_large", True
                return _error_result(
                    ErrorEnvelope(
                        code="output_too_large",
                        message=f"Result is {size} bytes; the cap is {rt.policy.max_output_bytes} bytes.",
                        hint="Narrow the request: smaller page_size, fewer ids, or include_sections=false.",
                        details={"limit_bytes": rt.policy.max_output_bytes, "actual_bytes": size},
                    )
                )
            outcome, is_error = _outcome(result)
            return result
        except MCPError as exc:
            if exc.code != RATE_LIMITED_CODE:
                outcome, is_error = f"error:{exc.code}", True
            raise
        finally:
            duration = (time.perf_counter() - start) * 1000
            record["outcome"] = outcome
            record["duration_ms"] = round(duration, 3)
            rt.metrics.record(tool, duration, error=is_error, rate_limited=limited)
            rt.audit.write(record)

    return safety


async def _verify_read_only(server: MCPServer[Any], rt: Runtime) -> None:
    tools = await server.list_tools()
    offenders = [
        t.name
        for t in tools
        if t.annotations is None
        or t.annotations.read_only_hint is not True
        or t.annotations.destructive_hint is True
    ]
    if offenders:
        raise MCPError(
            INTERNAL_ERROR,
            "finos-mcp refuses to serve tools without read-only annotations",
            {"tools": offenders},
        )
    rt.known_tools = frozenset(t.name for t in tools)
    rt.read_only_verified = True


def build_server(
    name: str,
    *,
    version: str,
    instructions: str,
    policy: SafetyPolicy | None = None,
    audit: AuditLog | None = None,
    metrics: Metrics | None = None,
    clock: Callable[[], float] | None = None,
) -> MCPServer[Any]:
    """Create an `MCPServer` with the safety middleware installed.

    The policy is copied and tightened from the environment; the rate limiter is
    always built from that final policy so per-tool limits registered later apply.
    """
    pol = (policy or SafetyPolicy()).tightened_from_env()
    rt = Runtime(
        policy=pol,
        limiter=RateLimiter(pol, clock=clock),
        audit=audit or AuditLog.from_env(name, hash_inputs=pol.audit_hash_inputs),
        metrics=metrics or Metrics(),
        tool_names=[],
    )
    server: MCPServer[Any] = MCPServer(name, version=version, instructions=instructions)
    server.middleware.append(_make_middleware(server, rt))
    _RUNTIMES[server] = rt
    return server


def register_tool[F: Callable[..., Any]](
    server: MCPServer[Any],
    fn: F,
    *,
    name: str | None = None,
    title: str | None = None,
    description: str | None = None,
    limit: RateLimit | None = None,
    input_bytes: int | None = None,
) -> F:
    """Register `fn` as a read-only tool and record its policy overrides."""
    rt = runtime_for(server)
    tool_name = name or fn.__name__
    rt.policy.register(tool_name, limit=limit, input_bytes=input_bytes)
    rt.tool_names.append(tool_name)
    return server.tool(name=tool_name, title=title, description=description, annotations=READ_ONLY)(
        fn
    )


def register_server_info(
    server: MCPServer[Any],
    *,
    standard: str,
    standard_version: str | None,
    upstream_repo: str | None,
    upstream_ref: str | None,
    upstream_commit: str | None,
    counts: Callable[[], dict[str, int]],
    resources: Callable[[], list[str]] | None = None,
) -> None:
    rt = runtime_for(server)

    def server_info() -> ServerInfo:
        """Describe this server: standard version, upstream provenance, exposed counts, latency, policy."""
        return ServerInfo(
            name=server.name or "",
            version=server.version or "",
            standard=standard,
            standard_version=standard_version,
            upstream_repo=upstream_repo,
            upstream_ref=upstream_ref,
            upstream_commit=upstream_commit,
            counts=counts(),
            tools=sorted(rt.tool_names),
            resources=resources() if resources else [],
            latency=rt.metrics.snapshot(),
            policy={
                "max_input_bytes": rt.policy.max_input_bytes,
                "max_output_bytes": rt.policy.max_output_bytes,
                "default_limit": rt.policy.default_limit.model_dump(),
                "per_tool": {k: v.model_dump() for k, v in rt.policy.per_tool.items()},
            },
        )

    register_tool(server, server_info, name="server_info")


__all__ = [
    "READ_ONLY",
    "Runtime",
    "build_server",
    "canonical_json",
    "register_server_info",
    "register_tool",
    "runtime_for",
]
