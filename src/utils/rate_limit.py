"""
A simple in-memory fixed-window rate limiter, keyed by client host.

No conversation/draft content is retained — only per-key hit timestamps,
matching the stateless contract's "rate limiting may exist but must not
depend on retaining content" rule. Process-local: fine for a single
instance, not shared across replicas.
"""

from __future__ import annotations

import time
from collections import defaultdict
from functools import lru_cache

from fastapi import Depends, Request

from src.utils.config import get_settings
from src.utils.errors import api_error


_WINDOW_SECONDS = 60


class RateLimiter:
    """Tracks recent hit timestamps per key and rejects once `per_minute` is exceeded."""

    def __init__(self, per_minute: int) -> None:
        self._per_minute = per_minute
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.monotonic()
        window_start = now - _WINDOW_SECONDS
        recent_hits = [hit for hit in self._hits[key] if hit > window_start]

        if len(recent_hits) >= self._per_minute:
            self._hits[key] = recent_hits
            raise api_error(
                "RATE_LIMITED", "Too many requests. Please slow down and try again shortly."
            )

        recent_hits.append(now)
        self._hits[key] = recent_hits


@lru_cache(maxsize=1)
def get_rate_limiter() -> RateLimiter:
    """The process-wide limiter, built from `Settings.rate_limit`."""

    return RateLimiter(per_minute=get_settings().rate_limit.per_minute)


def enforce_rate_limit(request: Request, limiter: RateLimiter = Depends(get_rate_limiter)) -> None:
    """FastAPI dependency: raises `RATE_LIMITED` (429) once the caller's host exceeds the configured rate."""

    key = request.client.host if request.client else "unknown"
    limiter.check(key)
