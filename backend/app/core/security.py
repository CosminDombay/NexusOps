from __future__ import annotations

import re
import time
from collections import OrderedDict, deque
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.client_ip import client_ip_or_unknown
from backend.app.core.config import settings

logger = structlog.get_logger(__name__)

WINDOW_SECONDS = 60

# Path segments that are per-record identifiers. Collapsing them keeps one
# bucket per route instead of one per object id, which is what previously let
# the hit map grow without bound.
_UUID_SEGMENT = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_NUMERIC_SEGMENT = re.compile(r"^\d+$")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self' ws: wss: http: https:; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'",
        )
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """Small single-process limiter for baseline public-exposure readiness.

    Buckets live in a bounded LRU map: expired and least-recently-used entries
    are evicted so a caller cannot grow the map by varying the request path.
    """

    MAX_TRACKED_KEYS = 50_000

    def __init__(self, app, *, max_tracked_keys: int | None = None) -> None:
        super().__init__(app)
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._max_tracked_keys = max_tracked_keys or self.MAX_TRACKED_KEYS

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        source_ip = client_ip_or_unknown(request)
        limit = self._limit_for_path(request.url.path)
        key = f"{source_ip}:{request.method}:{self._bucket_path(request.url.path)}"
        now = time.monotonic()

        hits = self._touch(key, now)
        if len(hits) >= limit:
            logger.warning("security.rate_limited", path=request.url.path, source_ip=source_ip)
            return Response("Rate limit exceeded", status_code=status.HTTP_429_TOO_MANY_REQUESTS)
        hits.append(now)
        return await call_next(request)

    def _touch(self, key: str, now: float) -> deque[float]:
        """Return the live window for a key, evicting stale and overflow entries."""
        window_start = now - WINDOW_SECONDS
        hits = self._hits.get(key)
        if hits is None:
            hits = deque()
            self._hits[key] = hits
        else:
            self._hits.move_to_end(key)
        while hits and hits[0] < window_start:
            hits.popleft()

        # Drop the oldest buckets once the map is full. Anything evicted has
        # either expired or is the least recently used key.
        while len(self._hits) > self._max_tracked_keys:
            evicted_key, _ = self._hits.popitem(last=False)
            if evicted_key == key:  # pragma: no cover - only when max is 0
                self._hits[key] = hits
                break
        return hits

    @staticmethod
    def _bucket_path(path: str) -> str:
        segments = [
            ":id" if (_UUID_SEGMENT.match(segment) or _NUMERIC_SEGMENT.match(segment)) else segment
            for segment in path.split("/")
        ]
        return "/".join(segments)

    @staticmethod
    def _limit_for_path(path: str) -> int:
        if path.endswith("/auth/login"):
            return settings.login_rate_limit_per_minute
        if "/remote-access/" in path and path.endswith("/shell-token"):
            return settings.websocket_rate_limit_per_minute
        return settings.api_rate_limit_per_minute
