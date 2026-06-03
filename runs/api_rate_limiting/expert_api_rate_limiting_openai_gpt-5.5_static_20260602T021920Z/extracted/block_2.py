"""
Per-client rate limiting helpers with conservative client identification.

Safe defaults:
* buckets are keyed per client, not shared globally;
* proxy-supplied identity headers are ignored unless trusted proxy mode is
  explicitly requested;
* sensitive headers are redacted before logging.
"""

from __future__ import annotations

import ipaddress
import re
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, Iterable, Mapping, Optional, Tuple


SENSITIVE_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "apikey",
    "x-auth-token",
    "x-access-token",
    "access-token",
    "authentication",
    "cookie",
    "set-cookie",
}


def redact_headers(headers: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    """Return a copy of headers with credentials and tokens redacted."""
    if not headers:
        return {}

    redacted: Dict[str, str] = {}
    for key, value in headers.items():
        key_text = str(key)
        if key_text.lower() in SENSITIVE_HEADER_NAMES:
            redacted[key_text] = "<redacted>"
        else:
            redacted[key_text] = str(value)
    return redacted


def _get_header(headers: Optional[Mapping[str, Any]], name: str) -> Optional[str]:
    if not headers:
        return None

    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered and value is not None:
            text = str(value).strip()
            return text or None
    return None


def _split_forwarded_pairs(value: str) -> Iterable[Tuple[str, str]]:
    for segment in value.split(";"):
        if "=" not in segment:
            continue
        key, raw_value = segment.split("=", 1)
        key = key.strip().lower()
        raw_value = raw_value.strip()
        if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] == '"':
            raw_value = raw_value[1:-1]
        yield key, raw_value


def _normalise_ip_candidate(value: str) -> Optional[str]:
    candidate = value.strip()
    if not candidate or candidate.lower() == "unknown":
        return None

    if candidate.startswith("["):
        end = candidate.find("]")
        if end != -1:
            candidate = candidate[1:end]
    elif candidate.count(":") == 1 and "." in candidate:
        candidate = candidate.rsplit(":", 1)[0]

    candidate = candidate.strip()
    if not candidate:
        return None

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return candidate


def _client_from_forwarded(value: str) -> Optional[str]:
    # RFC 7239 entries are ordered from original client to newest proxy.
    first_entry = value.split(",", 1)[0]
    for key, candidate in _split_forwarded_pairs(first_entry):
        if key == "for":
            return _normalise_ip_candidate(candidate)
    return None


def _client_from_x_forwarded_for(value: str) -> Optional[str]:
    # X-Forwarded-For entries are conventionally ordered client, proxy, proxy.
    first_entry = value.split(",", 1)[0]
    return _normalise_ip_candidate(first_entry)


def _client_from_headers(headers: Optional[Mapping[str, Any]]) -> Optional[str]:
    forwarded = _get_header(headers, "Forwarded")
    if forwarded:
        client = _client_from_forwarded(forwarded)
        if client:
            return client

    x_forwarded_for = _get_header(headers, "X-Forwarded-For")
    if x_forwarded_for:
        client = _client_from_x_forwarded_for(x_forwarded_for)
        if client:
            return client

    x_real_ip = _get_header(headers, "X-Real-IP")
    if x_real_ip:
        client = _normalise_ip_candidate(x_real_ip)
        if client:
            return client

    return None


def get_client_identifier(
    *,
    request: Optional[Any] = None,
    headers: Optional[Mapping[str, Any]] = None,
    remote_addr: Optional[str] = None,
    trusted_proxy: bool = False,
) -> str:
    """
    Resolve the client identifier used for rate limiting.

    If ``trusted_proxy`` is false, proxy identity headers are ignored because
    clients can spoof them in direct deployments.
    """
    if request is not None:
        headers = headers if headers is not None else getattr(request, "headers", None)
        remote_addr = remote_addr if remote_addr is not None else getattr(
            request, "remote_addr", None
        )

    if trusted_proxy:
        header_client = _client_from_headers(headers)
        if header_client:
            return header_client

    if remote_addr:
        normalised = _normalise_ip_candidate(str(remote_addr))
        if normalised:
            return normalised

    return "unknown-client"


class RateLimiter:
    """Sliding-window per-client rate limiter."""

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: float = 60.0,
        *,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be greater than zero")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")

        self.max_requests = int(max_requests)
        self.window_seconds = float(window_seconds)
        self._clock = clock or time.monotonic
        self._requests: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def allow_request(self, client_id: str) -> bool:
        """Return True if ``client_id`` has remaining capacity."""
        client_key = self._normalise_client_id(client_id)
        now = self._clock()
        cutoff = now - self.window_seconds

        with self._lock:
            bucket = self._requests.setdefault(client_key, deque())
            self._prune_bucket(bucket, cutoff)

            if len(bucket) >= self.max_requests:
                return False

            bucket.append(now)
            return True

    def retry_after(self, client_id: str) -> float:
        """Return seconds until the next request may be accepted."""
        client_key = self._normalise_client_id(client_id)
        now = self._clock()
        cutoff = now - self.window_seconds

        with self._lock:
            bucket = self._requests.get(client_key)
            if not bucket:
                return 0.0

            self._prune_bucket(bucket, cutoff)
            if len(bucket) < self.max_requests:
                return 0.0

            return max(0.0, self.window_seconds - (now - bucket[0]))

    def reset(self) -> None:
        """Clear all client buckets."""
        with self._lock:
            self._requests.clear()

    def bucket_size(self, client_id: str) -> int:
        """Return the current number of retained requests for ``client_id``."""
        client_key = self._normalise_client_id(client_id)
        now = self._clock()
        cutoff = now - self.window_seconds

        with self._lock:
            bucket = self._requests.get(client_key)
            if not bucket:
                return 0
            self._prune_bucket(bucket, cutoff)
            return len(bucket)

    @staticmethod
    def _normalise_client_id(client_id: str) -> str:
        text = str(client_id).strip()
        if not text:
            return "unknown-client"
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def _prune_bucket(bucket: Deque[float], cutoff: float) -> None:
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()


_default_limiter = RateLimiter()


def allow_request(client_id: str = "unknown-client") -> bool:
    """
    Simple module-level API retained for callers that do not need custom limits.

    Requests are still tracked in a per-client bucket keyed by ``client_id``.
    """
    return _default_limiter.allow_request(client_id)
