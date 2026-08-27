from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]

_REPO_ROOT = Path(__file__).resolve().parents[3]
if load_dotenv is not None:
    load_dotenv(_REPO_ROOT / ".env", override=False)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from hawk_eye import __version__ as hawk_eye_version
from hawk_eye.backend.db import init_db
from hawk_eye.backend.http_latency_middleware import HttpLatencyMiddleware
from hawk_eye.backend.rate_limit import RateLimitMiddleware
from hawk_eye.backend.request_id import RequestIdMiddleware
from hawk_eye.backend.routes import (
    alert_router,
    auth_router,
    case_router,
    detect_router,
    export_router,
    gov_router,
    health_router,
    int_router,
    job_router,
    llm_router,
    rule_router,
    report_router,
    settings_router,
    status_router,
    suppression_router,
    tenant_router,
    ws_router,
)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db()
        import hawk_eye.backend.prometheus_extra  # noqa: F401 — register hawk_eye_lab_simulation_runs_total

        yield

    app = FastAPI(title="Hawk-Eye Dashboard Backend", version=hawk_eye_version, lifespan=lifespan)

    raw_origins = os.environ.get("HAWK_EYE_CORS_ORIGINS", "").strip()
    if raw_origins:
        origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
        if origins:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(HttpLatencyMiddleware)

    app.include_router(health_router)
    app.include_router(status_router)
    app.include_router(auth_router)
    app.include_router(tenant_router)
    app.include_router(settings_router)
    app.include_router(detect_router)
    app.include_router(llm_router)
    app.include_router(alert_router)
    app.include_router(case_router)
    app.include_router(rule_router)
    app.include_router(suppression_router)
    app.include_router(report_router)
    app.include_router(export_router)
    app.include_router(job_router)
    app.include_router(gov_router)
    app.include_router(int_router)
    app.include_router(ws_router)

    static_root = os.environ.get("HAWK_EYE_DASHBOARD_STATIC", "").strip()
    if static_root:
        p = Path(static_root).expanduser().resolve()
        if p.is_dir():
            app.mount("/app", StaticFiles(directory=str(p), html=True), name="dashboard_static")

    return app
