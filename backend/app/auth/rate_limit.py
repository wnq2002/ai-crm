"""登录限流（进程内滑动窗口，ADR-004）。

MVP 单进程部署下足够；多副本/多进程部署需外置存储（见 docs/decisions.md）。
"""

import time
from collections import defaultdict, deque
from threading import Lock

from app.core.config import settings


class SlidingWindowRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            dq = self._attempts[key]
            while dq and now - dq[0] > self.window_seconds:
                dq.popleft()
            if len(dq) >= self.max_attempts:
                return False
            dq.append(now)
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def reset_all(self) -> None:
        with self._lock:
            self._attempts.clear()


login_rate_limiter = SlidingWindowRateLimiter(
    settings.login_max_attempts, settings.login_window_seconds
)
