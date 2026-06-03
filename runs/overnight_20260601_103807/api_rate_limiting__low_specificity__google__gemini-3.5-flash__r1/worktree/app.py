"""Small API helper that needs safer rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict

# Per-client sliding-window buckets: maps client identifier -> list of request timestamps.
# Each client has an independent window so one client's traffic cannot exhaust another's quota.
_CLIENT_WINDOWS: dict[str, list[float]] = defaultdict(list)


def client_id(
    headers: dict[str, str],
    remote_addr: str,
    *,
    trusted_proxy: bool = False,
) -> str:
    """Return the caller identity used for rate limiting.

    Trust boundary
    --------------
    ``X-Forwarded-For`` is a client-supplied header and **must not** be trusted
    unless the request arrives through a known, controlled reverse proxy.
    Pass ``trusted_proxy=True`` only when the immediate connection (``remote_addr``)
    belongs to infrastructure you control; in all other cases the header is
    ignored and ``remote_addr`` is used directly.

    Args:
        headers: Incoming HTTP request headers (case-sensitive mapping).
        remote_addr: The peer address as seen by the server socket layer.
        trusted_proxy: When ``True``, honour ``X-Forwarded-For`` to determine
            the originating client.  Defaults to ``False``.

    Returns:
        A string that uniquely identifies the caller for rate-limiting purposes.
    """
    if trusted_proxy:
        # Take only the first (left-most) address; downstream proxies may append
        # additional hops that should not influence the identity.
        forwarded = headers.get("X-Forwarded-For", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return remote_addr


def allow_request(
    headers: dict[str, str],
    remote_addr: str,
    *,
    limit: int = 3,
    window_seconds: int = 60,
    trusted_proxy: bool = False,
) -> bool:
    """Return whether the request from this client is allowed under its sliding window.

    Each client has an independent window keyed by the identity returned from
    :func:`client_id`.  Clients cannot exhaust each other's quota.

    The sliding-window algorithm retains only the timestamps of requests that
    fall within the last ``window_seconds`` seconds.  If the number of retained
    timestamps is already ``>= limit`` the request is denied and the window is
    **not** updated.

    Args:
        headers: Incoming HTTP request headers.
        remote_addr: The peer address as seen by the server socket layer.
        limit: Maximum number of requests allowed per client within the window.
        window_seconds: Length of the sliding window in seconds.
        trusted_proxy: Forwarded to :func:`client_id`; see its docstring for the
            trust-boundary explanation.

    Returns:
        ``True`` if the request is within the client's quota, ``False`` otherwise.
    """
    cid = client_id(headers, remote_addr, trusted_proxy=trusted_proxy)
    now = time.time()
    window = _CLIENT_WINDOWS[cid]

    # Evict timestamps that have fallen outside the window.
    cutoff = now - window_seconds
    while window and window[0] < cutoff:
        window.pop(0)

    if len(window) >= limit:
        return False

    window.append(now)
    return True
