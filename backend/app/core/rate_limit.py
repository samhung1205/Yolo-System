"""
Small in-process sliding-window counter for failure-based throttling
(currently: failed logins).

State lives in this process's memory, which fits the single-worker
deployment; several uvicorn workers would each keep their own counts and a
shared store (e.g. Redis) would be needed instead.
"""
from __future__ import annotations

import math
import threading
import time
from collections import deque
from typing import Callable


class FailureWindow:
    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._events: dict[str, deque[float]] = {}

    def _prune(self, key: str, window_seconds: float, now: float) -> deque[float]:
        events = self._events.setdefault(key, deque())
        while events and events[0] <= now - window_seconds:
            events.popleft()
        return events

    def retry_after(self, key: str, *, limit: int, window_seconds: float) -> int:
        """Seconds until ``key`` may try again (0 = allowed now)."""
        if limit <= 0:
            return 0
        now = self._clock()
        with self._lock:
            events = self._prune(key, window_seconds, now)
            if len(events) < limit:
                if not events:
                    self._events.pop(key, None)
                return 0
            return max(1, math.ceil(events[0] + window_seconds - now))

    def record(self, key: str, *, window_seconds: float) -> None:
        now = self._clock()
        with self._lock:
            self._prune(key, window_seconds, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
