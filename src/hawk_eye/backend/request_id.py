"""Request ID propagation and optional JSON access logs."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_log = logging.getLogger("hawk_eye.access")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach X-Request-ID (reuse inbound header or generate UUID) on every response."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rid = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
        if not rid or not str(rid).strip():
            rid = str(uuid.uuid4())
        else:
            rid = str(rid).strip()[:128]
        request.state.request_id = rid
        start = time.perf_counter()
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        if os.environ.get("HAWK_EYE_LOG_JSON", "").strip().lower() in ("1", "true", "yes"):
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            line = {
                "msg": "access",
                "request_id": rid,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "elapsed_ms": round(elapsed_ms, 2),
            }
            _log.info(json.dumps(line, default=str))
        return response
