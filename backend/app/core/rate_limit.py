"""A small in-memory limiter: how many times one user may do something per window.

Enough for one service instance (the MVP runs as one); with several instances the limit
applies per instance."""

import time
from collections import deque

from app.core.exceptions import RateLimitedError


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= current - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(current)
        if len(self._hits) > 10_000:
            # Forget idle users so memory stays bounded.
            self._hits = {k: v for k, v in self._hits.items() if v}
        return True

    def check(self, key: str) -> None:
        if not self.allow(key):
            raise RateLimitedError(int(self.window))

    def reset(self) -> None:
        self._hits.clear()


# Questions to the assistant (app and bot together): the RAG service is the expensive part.
ask_limiter = RateLimiter(limit=10, window_seconds=60)
# «Сообщить о неточности»: a note per step is already de-duplicated; this stops floods.
report_limiter = RateLimiter(limit=20, window_seconds=3600)
