from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Deque, DefaultDict, Iterator, Optional, Tuple


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    window_seconds: float
    retry_after: float
    reset_after: float

    def __bool__(self) -> bool:
        return self.allowed

    def __iter__(self) -> Iterator[object]:
        # Backwards-friendly unpacking:
        #     allowed, retry_after = limiter.check(client_id)
        yield self.allowed
        yield self.retry_after


class SlidingWindowRateLimiter:
    """Simple in-memory per-client sliding-window rate limiter.

    The limiter stores one deque of request timestamps per client.  On each
    check, timestamps outside the current window are removed before deciding
    whether the request may proceed.  Different client identifiers therefore
    have independent request counts.
    """

    def __init__(
        self,
        max_requests: Optional[int] = None,
        window_seconds: Optional[float] = None,
        *,
        requests_per_window: Optional[int] = None,
        limit: Optional[int] = None,
        window_size_seconds: Optional[float] = None,
        window_size: Optional[float] = None,
        clock: Optional[Callable[[], float]] = None,
        time_provider: Optional[Callable[[], float]] = None,
    ) -> None:
        if max_requests is None:
            if requests_per_window is not None:
                max_requests = requests_per_window
            elif limit is not None:
                max_requests = limit
            else:
                max_requests = 60

        if window_seconds is None:
            if window_size_seconds is not None:
                window_seconds = window_size_seconds
            elif window_size is not None:
                window_seconds = window_size
            else:
                window_seconds = 60

        self.max_requests = int(max_requests)
        self.window_seconds = float(window_seconds)
        if self.max_requests < 0:
            raise ValueError("max_requests must be greater than or equal to zero")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")

        self._clock = clock or time_provider or time.monotonic
        self._requests: DefaultDict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.RLock()

    @property
    def requests(self) -> DefaultDict[str, Deque[float]]:
        """Expose request buckets for diagnostics/tests without copying."""

        return self._requests

    def _client_key(self, client_id: object) -> str:
        if client_id is None:
            return "anonymous"
        key = str(client_id)
        return key if key else "anonymous"

    def _prune(self, timestamps: Deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

    def _retry_after(self, timestamps: Deque[float], now: float) -> float:
        if not timestamps:
            return 0.0
        return float(max(0, math.ceil((timestamps[0] + self.window_seconds) - now)))

    def check(self, client_id: object) -> RateLimitResult:
        """Record a request if allowed and return the decision metadata."""

        key = self._client_key(client_id)
        now = float(self._clock())

        with self._lock:
            timestamps = self._requests[key]
            self._prune(timestamps, now)

            if self.max_requests == 0:
                retry_after = self.window_seconds
                return RateLimitResult(
                    allowed=False,
                    limit=self.max_requests,
                    remaining=0,
                    window_seconds=self.window_seconds,
                    retry_after=retry_after,
                    reset_after=retry_after,
                )

            if len(timestamps) >= self.max_requests:
                retry_after = self._retry_after(timestamps, now)
                return RateLimitResult(
                    allowed=False,
                    limit=self.max_requests,
                    remaining=0,
                    window_seconds=self.window_seconds,
                    retry_after=retry_after,
                    reset_after=retry_after,
                )

            timestamps.append(now)
            remaining = max(0, self.max_requests - len(timestamps))
            reset_after = self._retry_after(timestamps, now) or self.window_seconds
            return RateLimitResult(
                allowed=True,
                limit=self.max_requests,
                remaining=remaining,
                window_seconds=self.window_seconds,
                retry_after=0.0,
                reset_after=reset_after,
            )

    def status(self, client_id: object) -> RateLimitResult:
        """Return current limit status for a client without recording a hit."""

        key = self._client_key(client_id)
        now = float(self._clock())

        with self._lock:
            timestamps = self._requests[key]
            self._prune(timestamps, now)

            allowed = len(timestamps) < self.max_requests
            remaining = max(0, self.max_requests - len(timestamps))
            retry_after = 0.0 if allowed else self._retry_after(timestamps, now)
            reset_after = self._retry_after(timestamps, now)
            return RateLimitResult(
                allowed=allowed,
                limit=self.max_requests,
                remaining=remaining,
                window_seconds=self.window_seconds,
                retry_after=retry_after,
                reset_after=reset_after,
            )

    def is_allowed(self, client_id: object) -> bool:
        """Record a request and return only the allow/deny decision."""

        return self.check(client_id).allowed

    def allow(self, client_id: object) -> bool:
        """Alias for is_allowed."""

        return self.is_allowed(client_id)

    def allow_request(self, client_id: object) -> bool:
        """Alias for is_allowed."""

        return self.is_allowed(client_id)

    def hit(self, client_id: object) -> RateLimitResult:
        """Alias for check."""

        return self.check(client_id)

    def consume(self, client_id: object) -> RateLimitResult:
        """Alias for check."""

        return self.check(client_id)

    def remaining_for(self, client_id: object) -> int:
        return self.status(client_id).remaining

    def reset(self, client_id: object = None) -> None:
        with self._lock:
            if client_id is None:
                self._requests.clear()
            else:
                self._requests.pop(self._client_key(client_id), None)


RateLimiter = SlidingWindowRateLimiter
InMemoryRateLimiter = SlidingWindowRateLimiter

_default_limiter = SlidingWindowRateLimiter()


def check_rate_limit(
    client_id: object,
    rate_limiter: Optional[SlidingWindowRateLimiter] = None,
) -> Tuple[bool, float]:
    result = (rate_limiter or _default_limiter).check(client_id)
    return result.allowed, result.retry_after


def is_rate_limited(
    client_id: object,
    rate_limiter: Optional[SlidingWindowRateLimiter] = None,
) -> bool:
    return not (rate_limiter or _default_limiter).is_allowed(client_id)


def reset_rate_limits() -> None:
    _default_limiter.reset()
