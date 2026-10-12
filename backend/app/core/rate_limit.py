"""Per-client rate limiting (a sliding-window log, kept in memory).

In memory means per server instance: with Cloud Run capped at a few instances, a client
gets at most a few times the limit, which is enough to stop floods and password
guessing. A shared store (Redis) is the step up if the service ever scales wide.
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import Request


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Too many requests. Please wait a moment and try again.")
        self.retry_after = retry_after


class RateLimiter:
    """Allow `limit` requests per `window` seconds per client IP.

    Used as a FastAPI dependency: dependencies=[Depends(chat_limiter)].
    """

    MAX_TRACKED_CLIENTS = 10_000  # memory bound: idle clients are swept beyond this

    def __init__(
        self, limit: int, window: float, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()  # sync endpoints run in a thread pool

    def __call__(self, request: Request) -> None:
        # Behind Cloud Run, uvicorn's --proxy-headers puts the real client IP here.
        client = request.client.host if request.client else "unknown"
        self.check(client)

    def check(self, key: str) -> None:
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                retry_after = math.ceil(hits[0] + self.window - now)
                raise RateLimitExceeded(max(retry_after, 1))
            hits.append(now)
            if len(self._hits) > self.MAX_TRACKED_CLIENTS:
                self._sweep(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def _sweep(self, now: float) -> None:
        for key in [
            k for k, hits in self._hits.items() if not hits or hits[-1] <= now - self.window
        ]:
            del self._hits[key]


# The limits. Login is the strictest: it's the target for password guessing.
chat_limiter = RateLimiter(limit=20, window=60)
history_limiter = RateLimiter(limit=60, window=60)
login_limiter = RateLimiter(limit=10, window=15 * 60)

ALL_LIMITERS = (chat_limiter, history_limiter, login_limiter)
