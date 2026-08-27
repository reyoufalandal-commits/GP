from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# Simple in-memory sliding window: path -> list of timestamps per client key
_window: dict[str, list[float]] = defaultdict(list)
_MAX_PER_MINUTE = 120


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        p = request.url.path
        if p in ("/health", "/metrics", "/docs", "/openapi.json", "/redoc") or p.startswith("/api/v1/ws"):
            return await call_next(request)
        now = time.time()
        key = f"{_client_key(request)}:{request.url.path}"
        window = _window[key]
        cutoff = now - 60.0
        while window and window[0] < cutoff:
            window.pop(0)
        if len(window) >= _MAX_PER_MINUTE:
            return JSONResponse(
                {
                    "detail": (
                        "Rate limit exceeded (~120 requests per minute per client and path). "
                        "Wait a minute, reduce polling, or batch calls. See docs/ENVIRONMENT.md."
                    )
                },
                status_code=429,
            )
        window.append(now)
        return await call_next(request)
