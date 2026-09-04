"""Structured errors that an agent can act on.

Every failure the calling model could plausibly recover from is raised as a
`FinosToolError`, a `ToolError` whose message is a JSON `ErrorEnvelope`.  The MCP
SDK turns it into a `CallToolResult(is_error=True)` whose text the model reads.
Unexpected exceptions are deliberately *not* wrapped: the SDK logs the traceback
and shows the model only ``Error executing tool <name>``, so internals never leak.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import MCPError
from pydantic import BaseModel, Field

ErrorCode = Literal[
    "not_found",
    "ambiguous_id",
    "invalid_input",
    "input_too_large",
    "output_too_large",
    "validation_failed",
    "unsupported_format",
    "rate_limited",
    "internal",
]

# JSON-RPC error code used for rate limiting (server-defined range).
RATE_LIMITED_CODE = -32029


class ErrorEnvelope(BaseModel):
    """Machine-readable error body returned to the model."""

    code: ErrorCode
    message: str
    hint: str | None = None
    candidates: list[str] = Field(default_factory=list)
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)

    def to_text(self) -> str:
        return self.model_dump_json(exclude_none=True, exclude_defaults=True)

    @classmethod
    def parse_text(cls, text: str) -> ErrorEnvelope | None:
        """Best-effort parse of a tool error text back into an envelope.

        The MCP SDK prefixes tool errors with ``Error executing tool <name>: ``;
        parsing starts at the first ``{`` so both raw and prefixed forms work.
        """
        start = text.find("{")
        if start < 0:
            return None
        try:
            data = json.loads(text[start:])
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict) or "code" not in data:
            return None
        try:
            return cls.model_validate(data)
        except ValueError:
            return None


class FinosToolError(ToolError):
    """A `ToolError` carrying a structured `ErrorEnvelope`."""

    envelope: ErrorEnvelope

    def __init__(self, envelope: ErrorEnvelope) -> None:
        self.envelope = envelope
        super().__init__(envelope.to_text())


def not_found(kind: str, query: str, hint: str | None = None) -> FinosToolError:
    return FinosToolError(
        ErrorEnvelope(
            code="not_found",
            message=f"No {kind} matches {query!r}.",
            hint=hint,
            details={"kind": kind, "query": query},
        )
    )


def ambiguous(kind: str, query: str, candidates: list[str]) -> FinosToolError:
    return FinosToolError(
        ErrorEnvelope(
            code="ambiguous_id",
            message=f"{query!r} matches several {kind}s; pick one of the candidates.",
            hint=f"Call again with one exact id, e.g. {candidates[0]!r}." if candidates else None,
            candidates=candidates,
            details={"kind": kind, "query": query},
        )
    )


def invalid_input(message: str, hint: str | None = None, **details: Any) -> FinosToolError:
    return FinosToolError(
        ErrorEnvelope(code="invalid_input", message=message, hint=hint, details=details)
    )


def unsupported_format(message: str, hint: str | None = None, **details: Any) -> FinosToolError:
    return FinosToolError(
        ErrorEnvelope(code="unsupported_format", message=message, hint=hint, details=details)
    )


def rate_limited(tool: str, retry_after_s: float) -> MCPError:
    """Protocol-level rejection: the host sees a JSON-RPC error, not a tool result."""
    return MCPError(
        RATE_LIMITED_CODE,
        "rate_limited",
        {"tool": tool, "retry_after_s": round(retry_after_s, 3)},
    )
