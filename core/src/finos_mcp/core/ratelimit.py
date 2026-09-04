"""Token-bucket rate limiter keyed by (session, tool)."""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from .policy import RateLimit, SafetyPolicy

Clock = Callable[[], float]


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """Per-key token buckets with LRU eviction so session churn cannot exhaust memory."""

    def __init__(self, policy: SafetyPolicy, clock: Clock | None = None) -> None:
        self._policy = policy
        self._clock: Clock = clock or time.monotonic
        self._buckets: OrderedDict[tuple[str, str], _Bucket] = OrderedDict()

    @property
    def policy(self) -> SafetyPolicy:
        return self._policy

    def try_acquire(self, session: str, tool: str) -> tuple[bool, float]:
        """Consume one token. Returns (allowed, retry_after_seconds)."""
        limit: RateLimit = self._policy.limit_for(tool)
        now = self._clock()
        key = (session, tool)
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=float(limit.burst), updated=now)
            self._buckets[key] = bucket
            self._evict()
        else:
            self._buckets.move_to_end(key)
            elapsed = max(0.0, now - bucket.updated)
            bucket.tokens = min(float(limit.burst), bucket.tokens + elapsed * limit.rate_per_s)
            bucket.updated = now
        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True, 0.0
        deficit = 1.0 - bucket.tokens
        return False, deficit / limit.rate_per_s

    def _evict(self) -> None:
        while len(self._buckets) > self._policy.max_rate_keys:
            self._buckets.popitem(last=False)

    def reset(self) -> None:
        self._buckets.clear()

    def __len__(self) -> int:
        return len(self._buckets)
