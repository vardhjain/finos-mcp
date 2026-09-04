"""In-process call counters and latency reservoirs, exposed through `server_info`."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Any

RESERVOIR = 2000


@dataclass(slots=True)
class ToolStats:
    calls: int = 0
    errors: int = 0
    rate_limited: int = 0
    durations_ms: deque[float] = field(default_factory=lambda: deque(maxlen=RESERVOIR))

    def percentile(self, p: float) -> float | None:
        if not self.durations_ms:
            return None
        data = sorted(self.durations_ms)
        idx = min(len(data) - 1, max(0, round((p / 100.0) * (len(data) - 1))))
        return round(data[idx], 3)


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tools: dict[str, ToolStats] = {}

    def record(
        self, tool: str, duration_ms: float, *, error: bool = False, rate_limited: bool = False
    ) -> None:
        with self._lock:
            stats = self._tools.setdefault(tool, ToolStats())
            stats.calls += 1
            if error:
                stats.errors += 1
            if rate_limited:
                stats.rate_limited += 1
            else:
                stats.durations_ms.append(duration_ms)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                name: {
                    "calls": s.calls,
                    "errors": s.errors,
                    "rate_limited": s.rate_limited,
                    "p50_ms": s.percentile(50),
                    "p95_ms": s.percentile(95),
                    "p99_ms": s.percentile(99),
                }
                for name, s in sorted(self._tools.items())
            }

    def reset(self) -> None:
        with self._lock:
            self._tools.clear()
