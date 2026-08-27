"""Observe HTTP request duration for Prometheus (low-cardinality: no path labels)."""

from __future__ import annotations

import time

from prometheus_client import Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HTTP_REQUEST_DURATION = Histogram(
    "hawk_eye_http_request_duration_seconds",
    "Wall time for HTTP requests (middleware; includes routing and handlers)",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
)


class HttpLatencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        t0 = time.perf_counter()
        response: Response = await call_next(request)
        HTTP_REQUEST_DURATION.observe(time.perf_counter() - t0)
        return response
