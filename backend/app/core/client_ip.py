"""Trustworthy client-IP resolution for rate limiting and audit records.

``X-Forwarded-For`` is client-controlled: anything a caller sends arrives in the
header, and a reverse proxy that uses nginx's ``$proxy_add_x_forwarded_for``
*appends* the real peer address rather than replacing the chain. Reading the
leftmost entry therefore lets a caller pick their own identity, which defeats
per-IP rate limiting and forges the source IP on audit events.

The real peer is the entry ``TRUSTED_PROXY_HOPS`` from the right, counting one
hop per reverse proxy that is known to append. With no configured proxies the
header is ignored entirely and the socket peer is used.
"""

from __future__ import annotations

from typing import Protocol

from backend.app.core.config import settings

UNKNOWN_CLIENT = "unknown"


class _HasClient(Protocol):  # pragma: no cover - structural typing helper
    headers: object
    client: object


def client_ip(request: _HasClient | None, *, trusted_proxy_hops: int | None = None) -> str | None:
    """Resolve the originating client IP for a request or websocket connection."""
    if request is None:
        return None

    peer = getattr(getattr(request, "client", None), "host", None)
    hops = settings.trusted_proxy_hops if trusted_proxy_hops is None else trusted_proxy_hops
    if hops <= 0:
        return peer

    forwarded_for = request.headers.get("x-forwarded-for") if request.headers else None
    if not forwarded_for:
        return peer

    chain = [entry.strip() for entry in forwarded_for.split(",") if entry.strip()]
    if not chain:
        return peer

    # One trusted proxy appends one entry, so hop N from the right is the peer
    # that the outermost trusted proxy actually observed. A chain shorter than
    # the configured hop count means the request did not traverse the expected
    # proxies; fall back to the leftmost entry rather than trusting a forgery.
    index = len(chain) - hops
    return chain[index] if index >= 0 else chain[0]


def client_ip_or_unknown(request: _HasClient | None) -> str:
    """Rate-limit variant: never returns None so every caller gets a bucket."""
    return client_ip(request) or UNKNOWN_CLIENT
