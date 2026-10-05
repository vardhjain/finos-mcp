"""Safety policy: size caps and per-tool rate limits.

The policy can only be *tightened* from the environment; nothing here can turn
on write behaviour, because no write tool can be registered in the first place
(see `finos_mcp.core.server`).
"""

from __future__ import annotations

import math
import os
from typing import Any

from pydantic import BaseModel, Field

ENV_PREFIX = "FINOS_MCP_"


class RateLimit(BaseModel):
    """Token-bucket parameters: `calls` per `window_s`, with `burst` capacity."""

    calls: int = Field(default=60, ge=1)
    window_s: float = Field(default=60.0, gt=0)
    burst: int = Field(default=10, ge=1)

    @property
    def rate_per_s(self) -> float:
        return self.calls / self.window_s

    def tightened_by(self, other: RateLimit) -> RateLimit:
        """Return the stricter combination of two limits."""
        return RateLimit(
            calls=min(self.calls, other.calls),
            window_s=max(self.window_s, other.window_s),
            burst=min(self.burst, other.burst),
        )


_RESOURCE_METHODS = frozenset({"resources/read", "prompts/get"})


class SafetyPolicy(BaseModel):
    max_input_bytes: int = Field(default=64 * 1024, ge=256)
    max_output_bytes: int = Field(default=512 * 1024, ge=1024)
    default_limit: RateLimit = Field(default_factory=RateLimit)
    per_tool: dict[str, RateLimit] = Field(default_factory=dict)
    per_tool_input_bytes: dict[str, int] = Field(default_factory=dict)
    #: Budget for `resources/read` and `prompts/get`, each counted per session.
    resource_limit: RateLimit = Field(
        default_factory=lambda: RateLimit(calls=300, window_s=60.0, burst=60)
    )
    #: Set when MAX_INPUT_BYTES came from the environment: it then bounds every tool.
    input_ceiling: int | None = None
    max_search_results: int = Field(default=50, ge=1)
    audit_hash_inputs: bool = True
    max_rate_keys: int = Field(default=10_000, ge=16)

    def limit_for(self, tool: str) -> RateLimit:
        if tool in _RESOURCE_METHODS:
            return self.resource_limit
        return self.per_tool.get(tool, self.default_limit)

    def input_cap_for(self, tool: str) -> int:
        cap = self.per_tool_input_bytes.get(tool, self.max_input_bytes)
        # An operator's limit applies to the tools with their own, larger caps as well.
        return cap if self.input_ceiling is None else min(cap, self.input_ceiling)

    def register(
        self, tool: str, limit: RateLimit | None = None, input_bytes: int | None = None
    ) -> None:
        if limit is not None:
            self.per_tool[tool] = limit
        if input_bytes is not None:
            self.per_tool_input_bytes[tool] = input_bytes

    def tightened_from_env(self, env: dict[str, str] | None = None) -> SafetyPolicy:
        """Apply `FINOS_MCP_*` overrides. A looser value than the configured one is ignored."""
        e = os.environ if env is None else env
        updated = self.model_copy(deep=True)

        def _int(name: str) -> int | None:
            raw = e.get(ENV_PREFIX + name)
            if raw is None:
                return None
            try:
                return int(raw)
            except ValueError:
                return None

        def _float(name: str) -> float | None:
            raw = e.get(ENV_PREFIX + name)
            if raw is None:
                return None
            try:
                value = float(raw)
            except ValueError:
                return None
            return value if math.isfinite(value) else None

        def _positive(value: Any) -> Any:
            """An unusable rate value (zero, negative) is ignored like a non-numeric one,
            rather than crashing startup or disabling the limit."""
            return value if value is not None and value > 0 else None

        if (v := _int("MAX_INPUT_BYTES")) is not None:
            updated.max_input_bytes = max(256, min(updated.max_input_bytes, v))
            updated.input_ceiling = max(256, v)
        if (v := _int("MAX_OUTPUT_BYTES")) is not None:
            updated.max_output_bytes = max(1024, min(updated.max_output_bytes, v))
        calls = _positive(_int("RATE_CALLS"))
        window = _positive(_float("RATE_WINDOW_S"))
        burst = _positive(_int("RATE_BURST"))
        if calls is not None or window is not None or burst is not None:
            env_limit = RateLimit(
                calls=calls if calls is not None else updated.default_limit.calls,
                window_s=window if window is not None else updated.default_limit.window_s,
                burst=burst if burst is not None else updated.default_limit.burst,
            )
            updated.default_limit = updated.default_limit.tightened_by(env_limit)
            updated.per_tool = {k: v.tightened_by(env_limit) for k, v in updated.per_tool.items()}
            updated.resource_limit = updated.resource_limit.tightened_by(env_limit)
        raw_args = e.get(ENV_PREFIX + "AUDIT_RAW_ARGS")
        if raw_args is not None:
            updated.audit_hash_inputs = raw_args.strip().lower() not in {"1", "true", "yes"}
        return updated
