from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.config import settings

logger = structlog.get_logger(__name__)


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
    """Small single-process limiter for baseline public-exposure readiness."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)
        limit = self._limit_for_path(request.url.path)
        key = f"{self._client_ip(request)}:{request.method}:{request.url.path}"
        now = time.monotonic()
        window_start = now - 60
        hits = self._hits[key]
        while hits and hits[0] < window_start:
            hits.popleft()
        if len(hits) >= limit:
            logger.warning("security.rate_limited", path=request.url.path, source_ip=self._client_ip(request))
            return Response("Rate limit exceeded", status_code=status.HTTP_429_TOO_MANY_REQUESTS)
        hits.append(now)
        return await call_next(request)

    @staticmethod
    def _limit_for_path(path: str) -> int:
        if path.endswith("/auth/login"):
            return settings.login_rate_limit_per_minute
        if "/remote-access/" in path and path.endswith("/shell-token"):
            return settings.websocket_rate_limit_per_minute
        return settings.api_rate_limit_per_minute

    @staticmethod
    def _client_ip(request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
        return request.client.host if request.client else "unknown"
