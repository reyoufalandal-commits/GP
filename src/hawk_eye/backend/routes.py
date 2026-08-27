from __future__ import annotations


import csv
import hashlib
import os
import shutil
import io
import json
import sqlite3
import time
from collections import defaultdict
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from prometheus_client import Counter, generate_latest

from hawk_eye.backend.db import db_path, get_db, init_db
from hawk_eye.backend.detection_history_repo import insert_detection_history
from hawk_eye.backend.deps import current_user, require_roles
from hawk_eye.backend.passwords import api_key_hash, hash_password, verify_password
from hawk_eye.backend.detection_resolution import fusion_kwargs_for_profile, project_root, resolve_artifact_dirs
from hawk_eye.backend.ml_policy_version import fusion_policy_snapshot
from hawk_eye.backend.detection_settings_repo import effective_for_tenant_id, effective_for_user, upsert
from hawk_eye.backend.events import broadcast_sync
from hawk_eye.backend.jobs_runner import process_pending_jobs
from hawk_eye.backend.policies import apply_enabled_rules, is_suppressed
from hawk_eye.backend.stream_duration import parse_duration_to_seconds
from hawk_eye.backend.schemas import (
    AlertCreate,
    AlertStatusUpdate,
    ApiKeyCreate,
    CaseAssignCreate,
    CaseCommentCreate,
    CaseCreate,
    CaseUpdate,
    DetectionSettingsPatch,
    ExportJobCreate,
    ExplainRowRequest,
    LoginRequest,
    LogoutRequest,
    LlmFormatExplanationRequest,
    StreamIncidentReportRequest,
    StreamMarkdownExportBody,
    RefreshRequest,
    RuleCreate,
    ScoreRequest,
    StreamSessionCreate,
    SuppressionCreate,
    TenantCreate,
)
from hawk_eye.backend.tenant_scope import is_global_admin, sql_tenant_and, tenant_id_for_write
from hawk_eye.backend.stream_session_job import run_stream_collect_job
from hawk_eye.backend.ws_hub import hub
from hawk_eye.decision_fusion import fuse_decisions
from hawk_eye.detect_novel import attack_uncertain_dataframe
from hawk_eye.explain import explain_row_from_records
from hawk_eye.io import read_table
from hawk_eye.llm_format import (
    format_model_explanation,
    format_stream_incident_report,
    llm_capabilities,
    stream_summary_to_markdown,
    stream_worksheet_html,
)
from hawk_eye import __version__ as hawk_eye_version
from hawk_eye.bundle import load as load_bundle
from hawk_eye.live.dual_mode import prepare_input_dataframe, read_zeek_conn_log_with_fields, score_and_fuse_with_fusion_kwargs


REQ_COUNTER = Counter("hawk_eye_backend_requests_total", "Total backend API requests", ["endpoint"])

_MAX_CONN_LOG_UPLOAD_BYTES = 50 * 1024 * 1024

_LLM_STREAM_INCIDENT_RL: dict[str, list[float]] = defaultdict(list)
_LLM_STREAM_INCIDENT_MAX_PER_MIN = 15


def _rate_limit_llm_stream_incident(username: str) -> None:
    now = time.time()
    w = _LLM_STREAM_INCIDENT_RL[str(username)]
    cutoff = now - 60.0
    while w and w[0] < cutoff:
        w.pop(0)
    if len(w) >= _LLM_STREAM_INCIDENT_MAX_PER_MIN:
        raise HTTPException(
            status_code=429,
            detail="stream incident report rate limit (per user per minute); try again shortly",
        )
    w.append(now)


def _ts() -> int:
    return int(time.time())


def _token_for(prefix: str) -> str:
    nonce = uuid.uuid4().hex
    return hashlib.sha256(f"{prefix}:{_ts()}:{nonce}".encode("utf-8")).hexdigest()


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing authorization header")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="invalid authorization format")
    return parts[1].strip()


def _audit(actor: str, action: str, payload: dict[str, Any], tenant_id: int | None = None) -> None:
    with get_db() as db:
        db.execute(
            "INSERT INTO audit_events(actor, action, payload_json, created_at, tenant_id) VALUES(?, ?, ?, ?, ?)",
            (actor, action, json.dumps(payload), _ts(), tenant_id),
        )


def _effective_settings_for_request(
    user: dict[str, Any], db: Any, tenant_id: int | None
) -> tuple[dict[str, Any], int | None]:
    if tenant_id is not None:
        if not is_global_admin(user):
            raise HTTPException(403, detail="only global admin may query tenant_id")
        return effective_for_tenant_id(db, tenant_id)
    return effective_for_user(db, user)


def _patch_target_tenant(user: dict[str, Any], tenant_id: int | None) -> int | None:
    if is_global_admin(user):
        return tenant_id
    if tenant_id is not None:
        raise HTTPException(403, detail="only global admin may set tenant_id")
    utid = user.get("tenant_id")
    if utid is None:
        raise HTTPException(400, detail="tenant required to update detection settings")
    return int(utid)


def _applied_detection(
    eff: dict[str, Any],
    bin_dir: str,
    sup_dir: str,
    ano_dir: str,
    *,
    include_fusion: bool,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "active_dual_mode": eff["active_dual_mode"],
        "active_unsw_profile": eff["active_unsw_profile"],
        "artifact_dirs": {"binary_dir": bin_dir, "supervised_dir": sup_dir, "anomaly_dir": ano_dir},
    }
    if include_fusion:
        out["fusion"] = fusion_kwargs_for_profile(eff["active_unsw_profile"])
    return out


def _persist_detection_history(
    user: dict[str, Any],
    kind: str,
    row_count: int,
    detail: dict[str, Any] | None,
) -> None:
    """Best-effort insert; never raises to callers."""
    try:
        tid = user.get("tenant_id")
        tid_i = int(tid) if tid is not None else None
        uname = str(user.get("username") or "unknown")
        with get_db() as db:
            insert_detection_history(
                db,
                tenant_id=tid_i,
                kind=kind,
                row_count=row_count,
                detail=detail,
                actor_username=uname,
            )
    except Exception:  # noqa: BLE001
        pass


health_router = APIRouter(tags=["health"])
status_router = APIRouter(prefix="/api/v1", tags=["status"])
auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
tenant_router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])
detect_router = APIRouter(prefix="/api/v1/detections", tags=["detections"])
llm_router = APIRouter(prefix="/api/v1/llm", tags=["llm"])
alert_router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])
case_router = APIRouter(prefix="/api/v1/cases", tags=["cases"])
report_router = APIRouter(prefix="/api/v1/reports", tags=["reports"])
gov_router = APIRouter(prefix="/api/v1/governance", tags=["governance"])
int_router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
rule_router = APIRouter(prefix="/api/v1/rules", tags=["rules"])
suppression_router = APIRouter(prefix="/api/v1/suppressions", tags=["suppressions"])
export_router = APIRouter(prefix="/api/v1/export", tags=["export"])
job_router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])
settings_router = APIRouter(prefix="/api/v1/settings", tags=["settings"])
ws_router = APIRouter(prefix="/api/v1")


def _readiness_payload() -> dict[str, Any]:
    init_db()
    checks = {
        "db_file": {"path": str(Path("data/db/hawk_eye.db").resolve()), "exists": Path("data/db/hawk_eye.db").exists()},
        "binary_dir": {"path": str(Path("artifacts/hawk-eye-binary").resolve()), "exists": Path("artifacts/hawk-eye-binary").exists()},
        "supervised_dir": {"path": str(Path("artifacts/current").resolve()), "exists": Path("artifacts/current").exists()},
        "anomaly_dir": {"path": str(Path("artifacts/current_anomaly").resolve()), "exists": Path("artifacts/current_anomaly").exists()},
    }
    return {"ready": all(v["exists"] for v in checks.values()), "checks": checks}


@health_router.get("/health")
def health() -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="health").inc()
    return {"status": "ok", "service": "hawk-eye-backend"}


@health_router.get("/ready")
def ready() -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="ready").inc()
    return _readiness_payload()


@status_router.get("/status")
def api_v1_status() -> dict[str, Any]:
    """Aggregated readiness + LLM capability (no secrets). Safe for dashboard polling without N+1."""
    REQ_COUNTER.labels(endpoint="api_status").inc()
    r = _readiness_payload()
    return {
        "version": hawk_eye_version,
        "service": "hawk-eye-backend",
        "ready": r["ready"],
        "checks": r["checks"],
        "llm": llm_capabilities(),
    }


@status_router.get("/detection-history")
def api_v1_detection_history(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
    limit_jobs: int = Query(50, ge=1, le=200),
    limit_runs: int = Query(100, ge=1, le=500),
    limit_scored: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Same payload as ``GET /api/v1/detections/history`` — top-level path for proxies that only expose ``/api/v1/status``-style routes."""
    REQ_COUNTER.labels(endpoint="api_v1_detection_history").inc()
    return _detection_history_payload(user, limit_jobs, limit_runs, limit_scored)


@health_router.get("/metrics")
def metrics() -> Any:
    REQ_COUNTER.labels(endpoint="metrics").inc()
    return generate_latest()


@auth_router.post("/login")
def login(req: LoginRequest) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="login").inc()
    with get_db() as db:
        row = db.execute("SELECT id, username, password_hash, role, tenant_id FROM users WHERE username = ?", (req.username,)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="invalid credentials")
    ok, needs_rehash = verify_password(str(row["password_hash"]), req.password)
    if not ok:
        raise HTTPException(status_code=401, detail="invalid credentials")
    if needs_rehash:
        new_h = hash_password(req.password)
        with get_db() as db:
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_h, int(row["id"])))
    access = _token_for("access:" + req.username)
    family = uuid.uuid4().hex
    refresh = _token_for("refresh:" + req.username)
    with get_db() as db:
        db.execute(
            "INSERT INTO auth_tokens(token, user_id, issued_at, expires_at, revoked) VALUES(?, ?, ?, ?, 0)",
            (access, int(row["id"]), _ts(), _ts() + 60 * 60 * 24),
        )
        db.execute(
            "INSERT INTO refresh_tokens(token, user_id, family_id, issued_at, expires_at, revoked) VALUES(?, ?, ?, ?, ?, 0)",
            (refresh, int(row["id"]), family, _ts(), _ts() + 60 * 60 * 24 * 30),
        )
    _audit(req.username, "auth.login", {"user_id": int(row["id"])}, tenant_id=row["tenant_id"])
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "tenant_id": row["tenant_id"],
        },
    }


@auth_router.post("/refresh")
def refresh_token(req: RefreshRequest) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="auth_refresh").inc()
    with get_db() as db:
        row = db.execute(
            """
            SELECT t.user_id, t.expires_at, t.revoked, u.username, u.role, u.tenant_id, t.family_id
            FROM refresh_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token = ?
            """,
            (req.refresh_token,),
        ).fetchone()
    if not row or int(row["revoked"]) == 1 or int(row["expires_at"]) <= _ts():
        raise HTTPException(status_code=401, detail="invalid refresh token")
    access = _token_for("access:" + str(row["username"]))
    new_refresh = _token_for("refresh:" + str(row["username"]))
    with get_db() as db:
        db.execute("UPDATE refresh_tokens SET revoked = 1 WHERE token = ?", (req.refresh_token,))
        db.execute(
            "INSERT INTO auth_tokens(token, user_id, issued_at, expires_at, revoked) VALUES(?, ?, ?, ?, 0)",
            (access, int(row["user_id"]), _ts(), _ts() + 60 * 60 * 24),
        )
        db.execute(
            "INSERT INTO refresh_tokens(token, user_id, family_id, issued_at, expires_at, revoked) VALUES(?, ?, ?, ?, ?, 0)",
            (new_refresh, int(row["user_id"]), str(row["family_id"]), _ts(), _ts() + 60 * 60 * 24 * 30),
        )
    return {
        "access_token": access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@auth_router.post("/revoke-all")
def revoke_all_tokens(user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="auth_revoke_all").inc()
    uid = int(user["id"])
    with get_db() as db:
        db.execute("UPDATE auth_tokens SET revoked = 1 WHERE user_id = ?", (uid,))
        db.execute("UPDATE refresh_tokens SET revoked = 1 WHERE user_id = ?", (uid,))
    _audit(user["username"], "auth.revoke_all", {"user_id": uid}, tenant_id=user.get("tenant_id"))
    return {"ok": True}


@auth_router.post("/api-keys", response_model=dict[str, Any])
def create_api_key(
    req: ApiKeyCreate,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="api_key_create").inc()
    raw = "he_" + uuid.uuid4().hex + uuid.uuid4().hex[:16]
    key_hash = api_key_hash(raw)
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO api_keys(key_hash, name, user_id, tenant_id, created_at, revoked) VALUES(?, ?, ?, ?, ?, 0)",
            (key_hash, req.name, int(user["id"]), user.get("tenant_id"), _ts()),
        )
    _audit(user["username"], "api_key.create", {"name": req.name, "id": int(cur.lastrowid)}, tenant_id=user.get("tenant_id"))
    return {"ok": True, "id": int(cur.lastrowid), "api_key": raw, "warning": "store this key securely; it is not shown again"}


@auth_router.get("/api-keys")
def list_api_keys(user: dict[str, Any] = Depends(require_roles("admin", "analyst"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="api_key_list").inc()
    with get_db() as db:
        rows = db.execute(
            "SELECT id, name, tenant_id, created_at, revoked FROM api_keys WHERE user_id = ? ORDER BY id DESC",
            (int(user["id"]),),
        ).fetchall()
    return {"rows": [dict(r) for r in rows]}


@auth_router.delete("/api-keys/{key_id}")
def delete_api_key(key_id: int, user: dict[str, Any] = Depends(require_roles("admin", "analyst"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="api_key_delete").inc()
    with get_db() as db:
        row = db.execute("SELECT id FROM api_keys WHERE id = ? AND user_id = ?", (key_id, int(user["id"]))).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="api key not found")
        db.execute("UPDATE api_keys SET revoked = 1 WHERE id = ?", (key_id,))
    _audit(user["username"], "api_key.revoke", {"id": key_id}, tenant_id=user.get("tenant_id"))
    return {"ok": True}


@auth_router.post("/logout")
def logout(req: LogoutRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="logout").inc()
    token = req.token or _extract_bearer(authorization)
    with get_db() as db:
        db.execute("UPDATE auth_tokens SET revoked = 1 WHERE token = ?", (token,))
    _audit("system", "auth.logout", {"token_prefix": token[:8]})
    return {"ok": True}


@auth_router.get("/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="me").inc()
    return {"user": user}


@tenant_router.post("")
def create_tenant(req: TenantCreate, user: dict[str, Any] = Depends(require_roles("admin"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="tenant_create").inc()
    with get_db() as db:
        cur = db.execute("INSERT INTO tenants(name, created_at) VALUES(?, ?)", (req.name, _ts()))
    _audit(user["username"], "tenant.create", {"tenant_name": req.name}, tenant_id=user.get("tenant_id"))
    return {"ok": True, "tenant_id": int(cur.lastrowid)}


@tenant_router.get("")
def list_tenants(user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="tenant_list").inc()
    with get_db() as db:
        if is_global_admin(user):
            rows = db.execute("SELECT id, name, created_at FROM tenants ORDER BY id DESC").fetchall()
        elif user.get("tenant_id") is not None:
            rows = db.execute(
                "SELECT id, name, created_at FROM tenants WHERE id = ? ORDER BY id DESC",
                (int(user["tenant_id"]),),
            ).fetchall()
        else:
            rows = []
    return {"rows": [dict(r) for r in rows]}


@settings_router.get("/detection")
def get_detection_settings(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
    tenant_id: int | None = Query(None),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="settings_detection_get").inc()
    with get_db() as db:
        eff, scope = _effective_settings_for_request(user, db, tenant_id)
        bin_dir, sup_dir, ano_dir = resolve_artifact_dirs(None, None, None, eff)
    fusion = fusion_kwargs_for_profile(eff["active_unsw_profile"])
    return {
        "active_dual_mode": eff["active_dual_mode"],
        "active_unsw_profile": eff["active_unsw_profile"],
        "binary_dir": eff.get("binary_dir"),
        "supervised_dir": eff.get("supervised_dir"),
        "anomaly_dir": eff.get("anomaly_dir"),
        "effective_artifact_dirs": {"binary_dir": bin_dir, "supervised_dir": sup_dir, "anomaly_dir": ano_dir},
        "fusion_defaults_preview": fusion,
        "conn_log_path": eff.get("conn_log_path"),
        "stream_poll_seconds": eff.get("stream_poll_seconds"),
        "stream_duration_default_seconds": eff.get("stream_duration_default_seconds"),
        "scope_tenant_id": scope,
    }


@settings_router.patch("/detection")
def patch_detection_settings(
    req: DetectionSettingsPatch,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst")),
    tenant_id: int | None = Query(None),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="settings_detection_patch").inc()
    target = _patch_target_tenant(user, tenant_id)
    patch = req.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="no fields to update")
    try:
        with get_db() as db:
            upsert(db, tenant_id=target, patch=patch)
            eff, scope = effective_for_tenant_id(db, target)
            bin_dir, sup_dir, ano_dir = resolve_artifact_dirs(None, None, None, eff)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    _audit(
        user["username"],
        "settings.detection_patch",
        {"target_tenant_id": target, **patch},
        tenant_id=user.get("tenant_id"),
    )
    return {
        "ok": True,
        "active_dual_mode": eff["active_dual_mode"],
        "active_unsw_profile": eff["active_unsw_profile"],
        "binary_dir": eff.get("binary_dir"),
        "supervised_dir": eff.get("supervised_dir"),
        "anomaly_dir": eff.get("anomaly_dir"),
        "effective_artifact_dirs": {"binary_dir": bin_dir, "supervised_dir": sup_dir, "anomaly_dir": ano_dir},
        "conn_log_path": eff.get("conn_log_path"),
        "stream_poll_seconds": eff.get("stream_poll_seconds"),
        "stream_duration_default_seconds": eff.get("stream_duration_default_seconds"),
        "scope_tenant_id": scope,
    }


def _enrich_detection_rows(rows: list[dict[str, Any]], tenant_id: int | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with get_db() as db:
        for r in rows:
            sup = is_suppressed(db, payload=r, tenant_id=tenant_id)
            hits = apply_enabled_rules(db, r, tenant_id)
            rr = dict(r)
            rr["_suppressed"] = sup
            rr["_rule_hits"] = hits
            out.append(rr)
    return out


def _prepare_rows_for_attack_uncertain(df: pd.DataFrame, bin_dir: str) -> pd.DataFrame:
    """Map Zeek ``conn``-like rows or full feature rows to the active binary bundle contract."""
    bb = load_bundle(bin_dir)
    try:
        return prepare_input_dataframe(df, bb.feature_columns)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@detect_router.post("/score")
def score(req: ScoreRequest, user: dict[str, Any] = Depends(require_roles("admin", "analyst"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="det_score").inc()
    if not req.rows:
        raise HTTPException(status_code=400, detail="rows is required")
    with get_db() as db:
        eff, _ = effective_for_user(db, user)
        bin_dir, sup_dir, ano_dir = resolve_artifact_dirs(req.binary_dir, req.supervised_dir, req.anomaly_dir, eff)
    df = _prepare_rows_for_attack_uncertain(pd.DataFrame(req.rows), bin_dir)
    out = attack_uncertain_dataframe(
        df,
        binary_dir=bin_dir,
        supervised_dir=sup_dir,
        anomaly_dir=ano_dir,
    )
    records = out.to_dict(orient="records")
    tid = user.get("tenant_id")
    tid_i = int(tid) if tid is not None else None
    applied = _applied_detection(eff, bin_dir, sup_dir, ano_dir, include_fusion=False)
    body = {
        "rows": _enrich_detection_rows(records, tid_i),
        "applied": applied,
    }
    _persist_detection_history(
        user,
        "score",
        len(records),
        {"applied": applied},
    )
    return body


@detect_router.post("/triage")
def triage(req: ScoreRequest, user: dict[str, Any] = Depends(require_roles("admin", "analyst"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="det_triage").inc()
    if not req.rows:
        raise HTTPException(status_code=400, detail="rows is required")
    with get_db() as db:
        eff, _ = effective_for_user(db, user)
        bin_dir, sup_dir, ano_dir = resolve_artifact_dirs(req.binary_dir, req.supervised_dir, req.anomaly_dir, eff)
    fusion = fusion_kwargs_for_profile(eff["active_unsw_profile"])
    df = pd.DataFrame(req.rows)
    if "binary_prediction" not in df.columns:
        df = _prepare_rows_for_attack_uncertain(df, bin_dir)
        df = attack_uncertain_dataframe(
            df,
            binary_dir=bin_dir,
            supervised_dir=sup_dir,
            anomaly_dir=ano_dir,
        )
    out = fuse_decisions(
        df,
        open_set_col="open_set_ood_score" if "open_set_ood_score" in df.columns else None,
        **fusion,
    )
    records = out.to_dict(orient="records")
    tid = user.get("tenant_id")
    tid_i = int(tid) if tid is not None else None
    applied = _applied_detection(eff, bin_dir, sup_dir, ano_dir, include_fusion=True)
    body = {
        "rows": _enrich_detection_rows(records, tid_i),
        "applied": applied,
    }
    _persist_detection_history(
        user,
        "triage",
        len(records),
        {"applied": applied},
    )
    return body


@detect_router.post("/triage-conn-log-file")
async def triage_conn_log_file(
    file: UploadFile = File(...),
    user: dict[str, Any] = Depends(require_roles("admin", "analyst")),
) -> dict[str, Any]:
    """One-shot triage: upload a Zeek tab-separated ``conn.log`` slice; same fusion as ``POST /triage``."""
    REQ_COUNTER.labels(endpoint="det_triage_conn_log_file").inc()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")
    if len(raw) > _MAX_CONN_LOG_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="file too large (max 50MB)")
    root = db_path().resolve().parents[2] / "data" / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    tmp_path = root / f"conn_{uuid.uuid4().hex}.log"
    try:
        tmp_path.write_bytes(raw)
        df_raw = read_zeek_conn_log_with_fields(tmp_path)
        if df_raw.empty:
            raise HTTPException(
                status_code=400,
                detail="no Zeek data rows in file (expect #fields header and tab-separated lines)",
            )
        with get_db() as db:
            eff, _ = effective_for_user(db, user)
            bin_dir, sup_dir, ano_dir = resolve_artifact_dirs(None, None, None, eff)
        bb = load_bundle(bin_dir)
        try:
            X = prepare_input_dataframe(df_raw, bb.feature_columns)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        fusion = fusion_kwargs_for_profile(eff["active_unsw_profile"])
        out = score_and_fuse_with_fusion_kwargs(
            X,
            binary_dir=bin_dir,
            supervised_dir=sup_dir,
            anomaly_dir=ano_dir,
            fusion_kwargs=fusion,
        )
        records = out.to_dict(orient="records")
        tid = user.get("tenant_id")
        tid_i = int(tid) if tid is not None else None
        applied = _applied_detection(eff, bin_dir, sup_dir, ano_dir, include_fusion=True)
        fn = file.filename or "upload"
        body = {
            "rows": _enrich_detection_rows(records, tid_i),
            "applied": applied,
            "source_filename": fn,
        }
        _persist_detection_history(
            user,
            "triage_conn_log",
            len(records),
            {"applied": applied, "source_filename": fn},
        )
        return body
    finally:
        tmp_path.unlink(missing_ok=True)


def _repo_lab_sim_conn_log_if_exists() -> str | None:
    """Use ``data/lab/sim_conn.log`` under the project root when present (see ``scripts/lab_simulate_conn_log.py``)."""
    p = project_root() / "data" / "lab" / "sim_conn.log"
    return str(p.resolve()) if p.is_file() else None


def _repo_live_conn_log_if_exists() -> str | None:
    """Use ``data/live/conn.log`` when Zeek is writing there (see ``scripts/zeek_network_capture.sh``)."""
    p = project_root() / "data" / "live" / "conn.log"
    return str(p.resolve()) if p.is_file() else None


def _first_nonempty_str(*candidates: object) -> str | None:
    for c in candidates:
        if c is None:
            continue
        s = str(c).strip()
        if s:
            return s
    return None


def _resolve_zeek_binary() -> tuple[bool, str | None]:
    """``shutil.which`` plus common install locations (Homebrew, Zeek.org packages)."""
    z = shutil.which("zeek")
    if z:
        return True, z
    for candidate in (
        "/opt/homebrew/bin/zeek",
        "/usr/local/bin/zeek",
        "/usr/local/zeek/bin/zeek",
        "/opt/zeek/bin/zeek",
    ):
        p = Path(candidate)
        if p.is_file():
            return True, str(p)
    return False, None


def _resolve_stream_conn_log(req_conn: str | None, eff: dict[str, Any]) -> tuple[str | None, str | None]:
    """
    Single resolution chain for Live stream (matches POST /stream-session).

    Returns ``(absolute_path, source_key)`` where source_key is for dashboards (e.g. ``detection_settings``).
    """
    candidates: list[tuple[str, object | None]] = [
        ("request", req_conn),
        ("detection_settings", eff.get("conn_log_path")),
        ("env_default", os.environ.get("HAWK_EYE_DEFAULT_CONN_LOG")),
        ("env_live", os.environ.get("HAWK_EYE_LIVE_CONN_LOG")),
        ("live_capture_file", _repo_live_conn_log_if_exists()),
        ("lab_sim_file", _repo_lab_sim_conn_log_if_exists()),
    ]
    for source, raw in candidates:
        s = _first_nonempty_str(raw)
        if s:
            return str(Path(s).expanduser().resolve()), source
    return None, None


@detect_router.get("/stream-hints")
def stream_log_hints(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict[str, Any]:
    """
    Paths and tooling hints for Live stream: Zeek network capture vs lab sim.

    The dashboard uses this to prefill ``conn_log_path`` for ``data/live/conn.log``.
    """
    REQ_COUNTER.labels(endpoint="det_stream_hints").inc()
    root = project_root().resolve()
    live_p = root / "data" / "live" / "conn.log"
    lab_p = root / "data" / "lab" / "sim_conn.log"
    zeek_ok, zeek = _resolve_zeek_binary()
    with get_db() as db:
        eff, _ = effective_for_user(db, user)
    resolved, resolved_src = _resolve_stream_conn_log(None, eff)

    live_exists = live_p.is_file()
    live_mtime_epoch: float | None = None
    live_size: int | None = None
    live_age_sec: float | None = None
    # Heuristic: Zeek appends to conn.log; mtime updates when new lines land.
    live_active_capture = False
    if live_exists:
        st = live_p.stat()
        live_mtime_epoch = float(st.st_mtime)
        live_size = int(st.st_size)
        age = time.time() - st.st_mtime
        live_age_sec = round(max(0.0, age), 3)
        # Zeek may write in bursts; treat recent mtime as "capture active" for the readiness strip.
        live_active_capture = age <= 90.0

    return {
        "repo_root": str(root),
        "live_conn_log_abs": str(live_p.resolve()),
        "live_conn_log_exists": live_exists,
        "live_conn_log_mtime_epoch": live_mtime_epoch,
        "live_conn_log_size_bytes": live_size,
        "live_conn_log_age_sec": live_age_sec,
        "live_conn_log_active_capture": live_active_capture,
        "lab_sim_conn_log_abs": str(lab_p.resolve()) if lab_p.is_file() else None,
        "zeek_in_path": zeek_ok,
        "zeek_path": zeek,
        "capture_script_rel": "scripts/zeek_network_capture.sh",
        "resolved_if_empty": resolved,
        "resolved_source": resolved_src,
    }


def _detection_history_payload(
    user: dict[str, Any],
    limit_jobs: int,
    limit_runs: int,
    limit_scored: int,
) -> dict[str, Any]:
    """Stream jobs, API detection runs, and recent batch ``scored_events`` rows (tenant-scoped)."""
    REQ_COUNTER.labels(endpoint="det_history").inc()
    extra_b, params_b = sql_tenant_and(user, "b")
    extra_h, params_h = sql_tenant_and(user, "h")
    extra_s, params_s = sql_tenant_and(user, "s")

    def _rows(rs: Any) -> list[dict[str, Any]]:
        return [dict(r) for r in rs]

    def _fetch(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> list[sqlite3.Row]:
        try:
            return list(conn.execute(sql, params).fetchall())
        except sqlite3.OperationalError:
            return []

    with get_db() as db:
        job_rows = _fetch(
            db,
            f"""
            SELECT b.id, b.status, b.created_at, b.updated_at, b.result_path, b.error,
                   a.parquet_path, a.summary_json_path, a.state_json_path
            FROM background_jobs b
            LEFT JOIN stream_job_artifact_index a ON a.job_id = b.id
            WHERE b.job_type = 'stream_collect' {extra_b}
            ORDER BY b.id DESC LIMIT ?
            """,
            (*params_b, limit_jobs),
        )
        run_rows = _fetch(
            db,
            f"""
            SELECT h.id, h.kind, h.created_at, h.row_count, h.detail_json, h.actor_username
            FROM detection_history h
            WHERE 1=1 {extra_h}
            ORDER BY h.id DESC LIMIT ?
            """,
            (*params_h, limit_runs),
        )
        scored_rows = _fetch(
            db,
            f"""
            SELECT s.id, s.row_id, s.score, s.label, s.model_version, s.created_at,
                   substr(s.raw_json, 1, 400) AS raw_json_preview
            FROM scored_events s
            WHERE 1=1 {extra_s}
            ORDER BY s.id DESC LIMIT ?
            """,
            (*params_s, limit_scored),
        )

    return {
        "stream_jobs": _rows(job_rows),
        "detection_runs": _rows(run_rows),
        "scored_events_recent": _rows(scored_rows),
    }


@detect_router.get("/history")
def detection_history_bundle(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
    limit_jobs: int = Query(50, ge=1, le=200),
    limit_runs: int = Query(100, ge=1, le=500),
    limit_scored: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Same payload as ``GET /api/v1/reports/detection-history``."""
    return _detection_history_payload(user, limit_jobs, limit_runs, limit_scored)


@detect_router.get("/last-stream-job")
def get_last_stream_job(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="det_last_stream_job").inc()
    snap = _last_stream_job_snapshot(user)
    if snap is None:
        return {"last_stream_job": None}
    return {"last_stream_job": snap}


@detect_router.post("/stream-session")
def start_stream_session(
    req: StreamSessionCreate,
    background_tasks: BackgroundTasks,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="det_stream_session").inc()
    with get_db() as db:
        eff, _ = effective_for_user(db, user)
        bin_dir, sup_dir, ano_dir = resolve_artifact_dirs(req.binary_dir, req.supervised_dir, req.anomaly_dir, eff)
    duration_s = parse_duration_to_seconds(req.duration, max_seconds=604800)
    conn_path, _conn_src = _resolve_stream_conn_log(req.conn_log_path, eff)
    if not conn_path:
        raise HTTPException(
            status_code=400,
            detail=(
                "conn_log_path is required: set it on Live stream or under Detection settings, "
                "run Zeek to data/live/conn.log (./scripts/zeek_network_capture.sh <iface>), "
                "or create data/lab/sim_conn.log (python scripts/lab_simulate_conn_log.py --out data/lab/sim_conn.log), "
                "or set env HAWK_EYE_DEFAULT_CONN_LOG / HAWK_EYE_LIVE_CONN_LOG."
            ),
        )
    poll = float(req.poll_seconds) if req.poll_seconds is not None else float(eff.get("stream_poll_seconds") or 2.0)
    fusion = fusion_kwargs_for_profile(eff["active_unsw_profile"])
    root = db_path().resolve().parents[2] / "data" / "stream_sessions"
    root.mkdir(parents=True, exist_ok=True)
    tid = user.get("tenant_id")
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO background_jobs(tenant_id, job_type, payload_json, status, created_at, updated_at) VALUES(?, ?, ?, 'pending', ?, ?)",
            (tid, "stream_collect", "{}", _ts(), _ts()),
        )
        jid = int(cur.lastrowid)
        state_path = root / f"job_{jid}_state.json"
        out_path = root / f"job_{jid}_scored.parquet"
        progress_path = root / f"job_{jid}_progress.json"
        payload = {
            "duration_seconds": duration_s,
            "conn_log_path": str(Path(conn_path).resolve()),
            "poll_seconds": poll,
            "binary_dir": bin_dir,
            "supervised_dir": sup_dir,
            "anomaly_dir": ano_dir,
            "fusion": fusion,
            "state_path": str(state_path.resolve()),
            "output_path": str(out_path.resolve()),
            "progress_path": str(progress_path.resolve()),
            "alert_log_path": req.alert_log_path,
            "webhook_url": req.webhook_url,
            "webhook_only_known_attack": bool(req.webhook_only_known_attack),
        }
        db.execute(
            "UPDATE background_jobs SET payload_json = ? WHERE id = ?",
            (json.dumps(payload), jid),
        )
    background_tasks.add_task(run_stream_collect_job, jid)
    _audit(
        user["username"],
        "detection.stream_session",
        {"job_id": jid, "duration_seconds": duration_s, "conn_log_path": str(conn_path)},
        tenant_id=tid,
    )
    return {
        "ok": True,
        "job_id": jid,
        "status": "pending",
        "duration_seconds": duration_s,
        "conn_log_path": str(Path(conn_path).resolve()),
        "conn_log_source": _conn_src,
        "poll_seconds": poll,
    }


@detect_router.post("/explain")
def explain_detection_row(
    req: ExplainRowRequest,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="det_explain").inc()
    with get_db() as db:
        eff, _ = effective_for_user(db, user)
        _, sup_dir, _ = resolve_artifact_dirs(None, req.supervised_dir, None, eff)
    try:
        payload = explain_row_from_records(
            bundle_dir=sup_dir,
            row_dict=req.row,
            row_index=req.row_index,
            top_k=req.top_k,
            redact=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"explain failed: {e}") from e
    return {"explain": payload, "supervised_dir": sup_dir}


@detect_router.get("/supervised-feature-schema")
def supervised_feature_schema(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict[str, Any]:
    """
    Return the active supervised bundle's ``feature_columns`` (exact names required for
    :func:`explain_row_from_records` and for rows that include all model inputs).
    """
    REQ_COUNTER.labels(endpoint="det_supervised_schema").inc()
    with get_db() as db:
        eff, _ = effective_for_user(db, user)
        _, sup_dir, _ = resolve_artifact_dirs(None, None, None, eff)
    try:
        b = load_bundle(sup_dir)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"cannot load supervised bundle: {e}") from e
    return {
        "supervised_dir": str(sup_dir),
        "feature_columns": b.feature_columns,
        "n_features": len(b.feature_columns),
    }


@detect_router.get("/lab-sample-rows")
def lab_sample_rows(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict[str, Any]:
    """
    Fixed JSON rows matching ``scripts/ci_build_minimal_bundles.py`` feature columns — for offline demos
    without crafting JSON by hand. The third row is tuned so **Full triage** on default minimal bundles
    surfaces the heuristic ``Suspected_ZeroDay`` label and ``AttackUncertain`` fusion (not a real CVE).
    Clients should still verify columns match the active supervised bundle.
    """
    REQ_COUNTER.labels(endpoint="det_lab_sample").inc()
    p = project_root() / "data" / "lab" / "model_lab_sample_rows.json"
    if not p.is_file():
        raise HTTPException(
            status_code=404,
            detail="lab sample missing: data/lab/model_lab_sample_rows.json",
        )
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"invalid lab sample json: {e}") from e
    if not isinstance(raw, list) or not raw:
        raise HTTPException(status_code=500, detail="lab sample must be a non-empty JSON array")
    return {
        "rows": raw,
        "note": "Rows 1–2 are ordinary examples; row 3 is for testing heuristic zero-day-style triage with CI minimal bundles.",
    }


@llm_router.get("/capabilities")
def llm_capabilities_endpoint(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict[str, Any]:
    """Whether server-side LLM is configured (OpenAI-compatible; includes Deepseek). No secrets returned."""
    REQ_COUNTER.labels(endpoint="llm_capabilities").inc()
    return llm_capabilities()


@llm_router.post("/format-explanation")
def llm_format_explanation(
    body: LlmFormatExplanationRequest,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst")),
    use_llm: bool | None = Query(
        default=None,
        description="Omit for env default; false forces deterministic stub; true attempts API if key set.",
    ),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="llm_format").inc()
    try:
        return format_model_explanation(body.explain, use_llm=use_llm)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


def _stream_collect_job_for_user(user: dict[str, Any], job_id: int) -> dict[str, Any]:
    with get_db() as db:
        row = db.execute("SELECT * FROM background_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    if not is_global_admin(user):
        jtid = row["tenant_id"]
        utid = user.get("tenant_id")
        if utid is None:
            if jtid is not None:
                raise HTTPException(status_code=404, detail="job not found")
        else:
            if jtid is None or int(jtid) != int(utid):
                raise HTTPException(status_code=404, detail="job not found")
    job = dict(row)
    if str(job.get("job_type") or "") != "stream_collect":
        raise HTTPException(status_code=400, detail="not a stream_collect job")
    if str(job.get("status") or "") != "completed":
        raise HTTPException(status_code=409, detail="job has no summary yet (not completed)")
    return job


def _stream_sessions_root() -> Path:
    return (db_path().resolve().parents[2] / "data" / "stream_sessions").resolve()


def _load_summary_json_from_result_path(job: dict[str, Any]) -> dict[str, Any]:
    rp = job.get("result_path")
    if not rp:
        raise HTTPException(status_code=404, detail="missing result_path")
    stream_root = _stream_sessions_root()
    try:
        p = Path(str(rp)).expanduser().resolve()
        p.relative_to(stream_root)
    except ValueError as e:
        raise HTTPException(status_code=403, detail="result outside stream_sessions") from e
    if not p.is_file():
        raise HTTPException(status_code=404, detail="summary file missing")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail="invalid summary json") from e


def _scored_parquet_path_for_stream_job(job_id: int, job: dict[str, Any]) -> Path:
    stream_root = _stream_sessions_root()
    payload = json.loads(str(job.get("payload_json") or "{}"))
    out_s = payload.get("output_path")
    if out_s:
        p = Path(str(out_s)).expanduser().resolve()
    else:
        p = (stream_root / f"job_{job_id}_scored.parquet").resolve()
    try:
        p.relative_to(stream_root)
    except ValueError as e:
        raise HTTPException(status_code=403, detail="output outside stream_sessions") from e
    return p


def _diff_stream_summaries(sa: dict[str, Any], sb: dict[str, Any]) -> dict[str, Any]:
    da = sa.get("decision_counts") or {}
    db_ = sb.get("decision_counts") or {}
    labels_dc = set(da.keys()) | set(db_.keys())
    ka = sa.get("known_attack_types") or {}
    kb = sb.get("known_attack_types") or {}
    labels_ka = set(ka.keys()) | set(kb.keys())
    return {
        "risk_level": [sa.get("risk_level"), sb.get("risk_level")],
        "attack_indicators": [sa.get("attack_indicators"), sb.get("attack_indicators")],
        "rows_scored": [sa.get("rows_scored"), sb.get("rows_scored")],
        "decision_counts": {str(lab): [int(da.get(lab, 0) or 0), int(db_.get(lab, 0) or 0)] for lab in sorted(labels_dc)},
        "known_attack_types": {
            str(lab): [int(ka.get(lab, 0) or 0), int(kb.get(lab, 0) or 0)] for lab in sorted(labels_ka)
        },
    }


def _last_stream_job_snapshot(user: dict[str, Any]) -> dict[str, Any] | None:
    extra, params = sql_tenant_and(user)
    with get_db() as db:
        row = db.execute(
            "SELECT id, status, created_at, updated_at, result_path, error FROM background_jobs WHERE job_type = 'stream_collect'"
            + extra
            + " ORDER BY id DESC LIMIT 1",
            params,
        ).fetchone()
    if not row:
        return None
    r = dict(row)
    risk: str | None = None
    if str(r.get("status") or "") == "completed" and r.get("result_path"):
        try:
            tmp = {"result_path": r["result_path"]}
            summ = _load_summary_json_from_result_path(tmp)
            rl = summ.get("risk_level")
            risk = str(rl) if rl is not None else None
        except HTTPException:
            risk = None
        except Exception:
            risk = None
    return {
        "job_id": int(r["id"]),
        "status": str(r.get("status") or ""),
        "risk_level": risk,
        "error": r.get("error"),
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
    }


@llm_router.post("/stream-incident-report")
def llm_stream_incident_report(
    body: StreamIncidentReportRequest,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst")),
    use_llm: bool | None = Query(
        default=None,
        description="Omit for env default; false forces deterministic stub; true uses OPENAI_API_KEY when set.",
    ),
    redact_ips: bool | None = Query(
        default=None,
        description="Omit for env default (HAWK_EYE_LLM_REDACT_IPS); mask IPv4 in sample_rows for external LLM.",
    ),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="llm_stream_incident").inc()
    _rate_limit_llm_stream_incident(user["username"])
    job = _stream_collect_job_for_user(user, body.job_id)
    rp = job.get("result_path")
    if not rp:
        raise HTTPException(status_code=404, detail="missing result_path")
    stream_root = (db_path().resolve().parents[2] / "data" / "stream_sessions").resolve()
    try:
        sp = Path(str(rp)).expanduser().resolve()
        sp.relative_to(stream_root)
    except ValueError as e:
        raise HTTPException(status_code=403, detail="result outside stream_sessions") from e
    if not sp.is_file():
        raise HTTPException(status_code=404, detail="summary file missing")
    try:
        summary = json.loads(sp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail="invalid summary json") from e

    payload = json.loads(str(job.get("payload_json") or "{}"))
    out_s = payload.get("output_path")
    jid = body.job_id
    if out_s:
        p = Path(str(out_s)).expanduser().resolve()
    else:
        p = (stream_root / f"job_{jid}_scored.parquet").resolve()
    try:
        p.relative_to(stream_root)
    except ValueError as e:
        raise HTTPException(status_code=403, detail="output outside stream_sessions") from e
    sample_rows: list[dict[str, Any]] = []
    if p.is_file():
        try:
            df = read_table(p)
            sub = df.tail(min(50, len(df)))
            sample_rows = json.loads(sub.to_json(orient="records", date_format="iso"))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"read parquet failed: {e}") from e

    try:
        return format_stream_incident_report(summary, sample_rows, use_llm=use_llm, redact_ips=redact_ips)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@alert_router.post("")
def create_alert(req: AlertCreate, user: dict[str, Any] = Depends(require_roles("admin", "analyst"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="alert_create").inc()
    try:
        tid = tenant_id_for_write(user, req.tenant_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    tid_i = int(tid) if tid is not None else None
    with get_db() as db:
        sup = is_suppressed(db, payload=req.payload, tenant_id=tid_i)
        hits = apply_enabled_rules(db, req.payload, tid_i)
        cur = db.execute(
            """
            INSERT INTO alerts(tenant_id, severity, title, decision_label, payload_json, status, suppressed, rule_hits_json, created_at)
            VALUES(?, ?, ?, ?, ?, 'new', ?, ?, ?)
            """,
            (
                tid,
                req.severity,
                req.title,
                req.decision_label,
                json.dumps(req.payload),
                1 if sup else 0,
                json.dumps(hits),
                _ts(),
            ),
        )
    aid = int(cur.lastrowid)
    _audit(
        user["username"],
        "alert.create",
        {"alert_id": aid, "severity": req.severity, "suppressed": sup, "rule_hits": hits},
        tenant_id=tid_i,
    )
    broadcast_sync({"type": "alert_created", "alert_id": aid, "suppressed": sup})
    return {"ok": True, "alert_id": aid, "suppressed": sup, "rule_hits": hits}


@alert_router.get("")
def list_alerts(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    from_ts: int | None = Query(None),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="alert_list").inc()
    extra, params = sql_tenant_and(user)
    q = "SELECT * FROM alerts WHERE 1=1" + extra
    p = list(params)
    if status:
        q += " AND status = ?"
        p.append(status)
    if from_ts is not None:
        q += " AND created_at >= ?"
        p.append(from_ts)
    q += " ORDER BY id DESC LIMIT ? OFFSET ?"
    p.extend([limit, offset])
    with get_db() as db:
        rows = db.execute(q, p).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d.pop("payload_json"))
        rh = d.pop("rule_hits_json", None)
        if rh:
            d["rule_hits"] = json.loads(rh)
        out.append(d)
    return {"rows": out, "limit": limit, "offset": offset}


@alert_router.patch("/{alert_id}/status")
def update_alert_status(
    alert_id: int,
    req: AlertStatusUpdate,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="alert_update_status").inc()
    allowed = {"new", "acknowledged", "in_progress", "resolved", "closed"}
    if req.status not in allowed:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(allowed)}")
    extra, params = sql_tenant_and(user)
    with get_db() as db:
        row = db.execute("SELECT * FROM alerts WHERE id = ?" + extra, (alert_id, *params)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="alert not found")
        db.execute("UPDATE alerts SET status = ? WHERE id = ?", (req.status, alert_id))
        row = db.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    _audit(user["username"], "alert.status_update", {"alert_id": alert_id, "status": req.status}, tenant_id=row["tenant_id"])
    d = dict(row)
    d["payload"] = json.loads(d.pop("payload_json"))
    rh = d.pop("rule_hits_json", None)
    if rh:
        d["rule_hits"] = json.loads(rh)
    broadcast_sync({"type": "alert_status", "alert_id": alert_id, "status": req.status})
    return {"row": d}


@case_router.post("")
def create_case(req: CaseCreate, user: dict[str, Any] = Depends(require_roles("admin", "analyst"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="case_create").inc()
    try:
        tid = tenant_id_for_write(user, req.tenant_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    with get_db() as db:
        if req.alert_id is not None:
            extra, params = sql_tenant_and(user)
            ar = db.execute("SELECT id FROM alerts WHERE id = ?" + extra, (req.alert_id, *params)).fetchone()
            if not ar:
                raise HTTPException(status_code=404, detail="alert not found")
        cur = db.execute(
            "INSERT INTO cases(tenant_id, title, status, priority, owner, alert_id, created_at, updated_at) VALUES(?, ?, 'new', ?, ?, ?, ?, ?)",
            (tid, req.title, req.priority, req.owner, req.alert_id, _ts(), _ts()),
        )
        cid = int(cur.lastrowid)
        db.execute(
            "INSERT INTO case_timeline(case_id, event_type, actor, payload_json, created_at) VALUES(?, ?, ?, ?, ?)",
            (cid, "case_created", user["username"], json.dumps({"title": req.title, "priority": req.priority}), _ts()),
        )
    _audit(user["username"], "case.create", {"case_id": cid}, tenant_id=tid)
    broadcast_sync({"type": "case_created", "case_id": cid})
    return {"ok": True, "case_id": cid}


@case_router.patch("/{case_id}")
def update_case(case_id: int, req: CaseUpdate, user: dict[str, Any] = Depends(require_roles("admin", "analyst"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="case_update").inc()
    extra, params = sql_tenant_and(user)
    with get_db() as db:
        row = db.execute("SELECT * FROM cases WHERE id = ?" + extra, (case_id, *params)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="case not found")
        db.execute("UPDATE cases SET status = ?, owner = ?, updated_at = ? WHERE id = ?", (req.status, req.owner, _ts(), case_id))
        row = db.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if row:
            db.execute(
                "INSERT INTO case_timeline(case_id, event_type, actor, payload_json, created_at) VALUES(?, ?, ?, ?, ?)",
                (case_id, "case_updated", user["username"], json.dumps({"status": req.status, "owner": req.owner}), _ts()),
            )
    _audit(user["username"], "case.update", {"case_id": case_id, "status": req.status}, tenant_id=row["tenant_id"])
    broadcast_sync({"type": "case_updated", "case_id": case_id, "status": req.status})
    return {"row": dict(row)}


@case_router.get("")
def list_cases(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="case_list").inc()
    extra, params = sql_tenant_and(user)
    q = "SELECT * FROM cases WHERE 1=1" + extra
    p = list(params)
    if status:
        q += " AND status = ?"
        p.append(status)
    q += " ORDER BY id DESC LIMIT ? OFFSET ?"
    p.extend([limit, offset])
    with get_db() as db:
        rows = db.execute(q, p).fetchall()
    return {"rows": [dict(r) for r in rows], "limit": limit, "offset": offset}


@case_router.get("/{case_id}/timeline")
def case_timeline(
    case_id: int,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="case_timeline").inc()
    extra, params = sql_tenant_and(user)
    with get_db() as db:
        c = db.execute("SELECT id FROM cases WHERE id = ?" + extra, (case_id, *params)).fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="case not found")
        rows = db.execute(
            "SELECT * FROM case_timeline WHERE case_id = ? ORDER BY id ASC",
            (case_id,),
        ).fetchall()
    return {"rows": [dict(r) for r in rows]}


@case_router.post("/{case_id}/comments")
def add_case_comment(
    case_id: int,
    req: CaseCommentCreate,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="case_comment_add").inc()
    extra, params = sql_tenant_and(user)
    with get_db() as db:
        exists = db.execute("SELECT id FROM cases WHERE id = ?" + extra, (case_id, *params)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="case not found")
        cur = db.execute(
            "INSERT INTO case_comments(case_id, author, comment, created_at) VALUES(?, ?, ?, ?)",
            (case_id, user["username"], req.comment, _ts()),
        )
    _audit(user["username"], "case.comment_add", {"case_id": case_id}, tenant_id=user.get("tenant_id"))
    return {"ok": True, "comment_id": int(cur.lastrowid)}


@case_router.get("/{case_id}/comments")
def list_case_comments(
    case_id: int,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="case_comment_list").inc()
    extra, params = sql_tenant_and(user)
    with get_db() as db:
        exists = db.execute("SELECT id FROM cases WHERE id = ?" + extra, (case_id, *params)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="case not found")
        rows = db.execute("SELECT * FROM case_comments WHERE case_id = ? ORDER BY id ASC", (case_id,)).fetchall()
    return {"rows": [dict(r) for r in rows]}


@case_router.post("/{case_id}/assign")
def assign_case(
    case_id: int,
    req: CaseAssignCreate,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="case_assign").inc()
    extra, params = sql_tenant_and(user)
    with get_db() as db:
        exists = db.execute("SELECT id FROM cases WHERE id = ?" + extra, (case_id, *params)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="case not found")
        db.execute("UPDATE cases SET owner = ?, updated_at = ? WHERE id = ?", (req.assignee, _ts(), case_id))
        cur = db.execute(
            "INSERT INTO case_assignments(case_id, assignee, assigned_by, created_at) VALUES(?, ?, ?, ?)",
            (case_id, req.assignee, user["username"], _ts()),
        )
    _audit(user["username"], "case.assign", {"case_id": case_id, "assignee": req.assignee}, tenant_id=user.get("tenant_id"))
    return {"ok": True, "assignment_id": int(cur.lastrowid)}


@case_router.get("/{case_id}/assignments")
def list_case_assignments(
    case_id: int,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="case_assignments").inc()
    extra, params = sql_tenant_and(user)
    with get_db() as db:
        exists = db.execute("SELECT id FROM cases WHERE id = ?" + extra, (case_id, *params)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="case not found")
        rows = db.execute("SELECT * FROM case_assignments WHERE case_id = ? ORDER BY id ASC", (case_id,)).fetchall()
    return {"rows": [dict(r) for r in rows]}


@report_router.get("/summary")
def report_summary(user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="report_summary").inc()
    extra, params = sql_tenant_and(user)
    with get_db() as db:
        alert_count = int(
            db.execute("SELECT COUNT(*) AS c FROM alerts WHERE 1=1" + extra, params).fetchone()["c"]
        )
        case_count = int(
            db.execute("SELECT COUNT(*) AS c FROM cases WHERE 1=1" + extra, params).fetchone()["c"]
        )
        open_case_count = int(
            db.execute(
                "SELECT COUNT(*) AS c FROM cases WHERE status NOT IN ('resolved', 'closed')" + extra,
                params,
            ).fetchone()["c"]
        )
    last_stream = _last_stream_job_snapshot(user)
    return {
        "alerts_total": alert_count,
        "cases_total": case_count,
        "cases_open": open_case_count,
        "last_stream_job": last_stream,
    }


@report_router.get("/detection-history")
def report_detection_history(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
    limit_jobs: int = Query(50, ge=1, le=200),
    limit_runs: int = Query(100, ge=1, le=500),
    limit_scored: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Same payload as ``GET /api/v1/detections/history`` — lives under reports for dashboards that already use ``/api/v1/reports/summary``."""
    return _detection_history_payload(user, limit_jobs, limit_runs, limit_scored)


@settings_router.get("/detection-history")
def settings_detection_history(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
    limit_jobs: int = Query(50, ge=1, le=200),
    limit_runs: int = Query(100, ge=1, le=500),
    limit_scored: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Same payload as ``GET /api/v1/detections/history`` — under settings for the dashboard Settings → Detection history page."""
    REQ_COUNTER.labels(endpoint="settings_detection_history").inc()
    return _detection_history_payload(user, limit_jobs, limit_runs, limit_scored)


@export_router.get("/alerts.csv")
def export_alerts_csv(user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer"))) -> StreamingResponse:
    REQ_COUNTER.labels(endpoint="export_alerts_csv").inc()
    extra, params = sql_tenant_and(user)
    with get_db() as db:
        rows = db.execute(
            "SELECT id, tenant_id, severity, title, decision_label, status, suppressed, created_at FROM alerts WHERE 1=1"
            + extra
            + " ORDER BY id DESC",
            params,
        ).fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "tenant_id", "severity", "title", "decision_label", "status", "suppressed", "created_at"])
    for r in rows:
        w.writerow(
            [r["id"], r["tenant_id"], r["severity"], r["title"], r["decision_label"], r["status"], r["suppressed"], r["created_at"]]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="alerts.csv"'},
    )


@export_router.get("/audit.json")
def export_audit_json(user: dict[str, Any] = Depends(require_roles("admin", "analyst"))) -> PlainTextResponse:
    REQ_COUNTER.labels(endpoint="export_audit_json").inc()
    extra, params = sql_tenant_and(user)
    with get_db() as db:
        rows = db.execute(
            "SELECT id, actor, action, payload_json, created_at, tenant_id FROM audit_events WHERE 1=1"
            + extra
            + " ORDER BY id DESC LIMIT 5000",
            params,
        ).fetchall()
    data = [dict(r) for r in rows]
    return PlainTextResponse(json.dumps(data, indent=2), media_type="application/json")


@job_router.post("")
def create_job(
    req: ExportJobCreate,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="job_create").inc()
    if req.job_type not in ("export_alerts_csv", "export_audit_json"):
        raise HTTPException(status_code=400, detail="invalid job_type")
    tid = user.get("tenant_id")
    if not is_global_admin(user) and tid is None:
        raise HTTPException(status_code=400, detail="tenant required for job")
    job_tid = None if is_global_admin(user) else int(tid)
    payload = json.dumps({"requested_by": user["username"]})
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO background_jobs(tenant_id, job_type, payload_json, status, created_at, updated_at) VALUES(?, ?, ?, 'pending', ?, ?)",
            (job_tid, req.job_type, payload, _ts(), _ts()),
        )
        jid = int(cur.lastrowid)
    process_pending_jobs(limit=5)
    with get_db() as db:
        row = db.execute("SELECT * FROM background_jobs WHERE id = ?", (jid,)).fetchone()
    return {"ok": True, "job": dict(row) if row else {"id": jid}}


@job_router.get("/compare-streams")
def compare_stream_jobs(
    job_a: int = Query(..., ge=1, description="First completed stream_collect job id"),
    job_b: int = Query(..., ge=1, description="Second completed stream_collect job id"),
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="job_compare_streams").inc()
    ja = _stream_collect_job_for_user(user, job_a)
    jb = _stream_collect_job_for_user(user, job_b)
    sa = _load_summary_json_from_result_path(ja)
    sb = _load_summary_json_from_result_path(jb)
    return {
        "job_a": job_a,
        "job_b": job_b,
        "summary_a": sa,
        "summary_b": sb,
        "diff": _diff_stream_summaries(sa, sb),
    }


@job_router.get("/{job_id}/stream-live-progress")
def get_stream_live_progress(
    job_id: int,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict[str, Any]:
    """Poll rows scored while a ``stream_collect`` job is running (Zeek appending to conn.log)."""
    REQ_COUNTER.labels(endpoint="job_stream_live_progress").inc()
    with get_db() as db:
        row = db.execute("SELECT * FROM background_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    if not is_global_admin(user):
        jtid = row["tenant_id"]
        utid = user.get("tenant_id")
        if utid is None:
            if jtid is not None:
                raise HTTPException(status_code=404, detail="job not found")
        else:
            if jtid is None or int(jtid) != int(utid):
                raise HTTPException(status_code=404, detail="job not found")
    job = dict(row)
    if str(job.get("job_type") or "") != "stream_collect":
        raise HTTPException(status_code=400, detail="not a stream_collect job")
    st = str(job.get("status") or "").strip().lower()
    stream_root = (db_path().resolve().parents[2] / "data" / "stream_sessions").resolve()
    payload = json.loads(str(job.get("payload_json") or "{}"))
    progress_s = payload.get("progress_path") or str(stream_root / f"job_{job_id}_progress.json")
    try:
        pp = Path(str(progress_s)).expanduser().resolve()
        pp.relative_to(stream_root)
    except ValueError as e:
        raise HTTPException(status_code=403, detail="progress path outside stream_sessions") from e

    if st == "completed":
        rp = job.get("result_path")
        if rp and Path(str(rp)).is_file():
            try:
                summary = json.loads(Path(str(rp)).read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                summary = {}
            return {
                "job_id": job_id,
                "job_status": "completed",
                "rows_scored": int(summary.get("rows_scored", 0)),
                "conn_log_line_offset": None,
                "updated_at": _ts(),
            }
    if st == "failed":
        return {"job_id": job_id, "job_status": "failed", "rows_scored": 0, "conn_log_line_offset": None, "updated_at": _ts()}

    if pp.is_file():
        try:
            data = json.loads(pp.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        return {
            "job_id": job_id,
            "job_status": st or "unknown",
            "rows_scored": int(data.get("rows_scored", 0)),
            "conn_log_line_offset": data.get("conn_log_line_offset"),
            "updated_at": data.get("updated_at"),
        }
    return {
        "job_id": job_id,
        "job_status": st or "pending",
        "rows_scored": 0,
        "conn_log_line_offset": None,
        "updated_at": None,
    }


@job_router.get("/{job_id}")
def get_job(job_id: int, user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="job_get").inc()
    with get_db() as db:
        row = db.execute("SELECT * FROM background_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    if not is_global_admin(user):
        jtid = row["tenant_id"]
        utid = user.get("tenant_id")
        if utid is None:
            if jtid is not None:
                raise HTTPException(status_code=404, detail="job not found")
        else:
            if jtid is None or int(jtid) != int(utid):
                raise HTTPException(status_code=404, detail="job not found")
    return {"job": dict(row)}


@job_router.get("/{job_id}/stream-summary")
def get_stream_job_summary(
    job_id: int,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict[str, Any]:
    """Return JSON written by a completed `stream_collect` job (``job_*_summary.json``)."""
    REQ_COUNTER.labels(endpoint="job_stream_summary").inc()
    with get_db() as db:
        row = db.execute("SELECT * FROM background_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    if not is_global_admin(user):
        jtid = row["tenant_id"]
        utid = user.get("tenant_id")
        if utid is None:
            if jtid is not None:
                raise HTTPException(status_code=404, detail="job not found")
        else:
            if jtid is None or int(jtid) != int(utid):
                raise HTTPException(status_code=404, detail="job not found")
    job = dict(row)
    if str(job.get("job_type") or "") != "stream_collect":
        raise HTTPException(status_code=400, detail="not a stream_collect job")
    if str(job.get("status") or "") != "completed":
        raise HTTPException(status_code=409, detail="job has no summary yet (not completed)")
    rp = job.get("result_path")
    if not rp:
        raise HTTPException(status_code=404, detail="missing result_path")
    stream_root = (db_path().resolve().parents[2] / "data" / "stream_sessions").resolve()
    try:
        p = Path(str(rp)).expanduser().resolve()
        p.relative_to(stream_root)
    except ValueError as e:
        raise HTTPException(status_code=403, detail="result outside stream_sessions") from e
    if not p.is_file():
        raise HTTPException(status_code=404, detail="summary file missing")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail="invalid summary json") from e


@job_router.get("/{job_id}/scored-preview")
def get_stream_scored_preview(
    job_id: int,
    limit: int = Query(50, ge=1, le=500),
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> dict[str, Any]:
    """Last ``limit`` rows from a completed ``stream_collect`` job Parquet (under ``data/stream_sessions``)."""
    REQ_COUNTER.labels(endpoint="job_scored_preview").inc()
    with get_db() as db:
        row = db.execute("SELECT * FROM background_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="job not found")
    if not is_global_admin(user):
        jtid = row["tenant_id"]
        utid = user.get("tenant_id")
        if utid is None:
            if jtid is not None:
                raise HTTPException(status_code=404, detail="job not found")
        else:
            if jtid is None or int(jtid) != int(utid):
                raise HTTPException(status_code=404, detail="job not found")
    job = dict(row)
    if str(job.get("job_type") or "") != "stream_collect":
        raise HTTPException(status_code=400, detail="not a stream_collect job")
    if str(job.get("status") or "") != "completed":
        raise HTTPException(status_code=409, detail="job not completed")
    stream_root = (db_path().resolve().parents[2] / "data" / "stream_sessions").resolve()
    payload = json.loads(str(job.get("payload_json") or "{}"))
    out_s = payload.get("output_path")
    if out_s:
        p = Path(str(out_s)).expanduser().resolve()
    else:
        p = (stream_root / f"job_{job_id}_scored.parquet").resolve()
    try:
        p.relative_to(stream_root)
    except ValueError as e:
        raise HTTPException(status_code=403, detail="output outside stream_sessions") from e
    if not p.is_file():
        raise HTTPException(status_code=404, detail="scored parquet not found")
    try:
        df = read_table(p)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"read parquet failed: {e}") from e
    sub = df.tail(limit)
    rows = json.loads(sub.to_json(orient="records", date_format="iso"))
    return {
        "job_id": job_id,
        "parquet_path": str(p),
        "total_rows": int(len(df)),
        "returned": int(len(sub)),
        "rows": rows,
    }


@job_router.post("/{job_id}/stream-markdown")
def export_stream_job_markdown(
    job_id: int,
    body: StreamMarkdownExportBody,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> PlainTextResponse:
    REQ_COUNTER.labels(endpoint="job_stream_markdown").inc()
    job = _stream_collect_job_for_user(user, job_id)
    summary = _load_summary_json_from_result_path(job)
    md = stream_summary_to_markdown(summary, incident_markdown=body.incident_markdown)
    return PlainTextResponse(
        md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="hawk-eye-stream-{job_id}.md"'},
    )


@job_router.get("/{job_id}/stream-worksheet")
def export_stream_job_worksheet(
    job_id: int,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> HTMLResponse:
    REQ_COUNTER.labels(endpoint="job_stream_worksheet").inc()
    job = _stream_collect_job_for_user(user, job_id)
    summary = _load_summary_json_from_result_path(job)
    html_doc = stream_worksheet_html(summary)
    return HTMLResponse(
        html_doc,
        headers={"Content-Disposition": f'attachment; filename="hawk-eye-worksheet-{job_id}.html"'},
    )


@job_router.get("/{job_id}/scored-parquet-file")
def download_stream_job_parquet(
    job_id: int,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
) -> FileResponse:
    REQ_COUNTER.labels(endpoint="job_scored_parquet_file").inc()
    job = _stream_collect_job_for_user(user, job_id)
    p = _scored_parquet_path_for_stream_job(job_id, job)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="scored parquet not found")
    return FileResponse(
        path=str(p),
        filename=f"job_{job_id}_scored.parquet",
        media_type="application/vnd.apache.parquet",
    )


@gov_router.get("/policy")
def governance_policy(user: dict[str, Any] = Depends(require_roles("admin", "analyst"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="gov_policy").inc()
    p = Path("config/governance_policy.json")
    if not p.exists():
        raise HTTPException(status_code=404, detail="governance policy not found")
    return json.loads(p.read_text())


@gov_router.get("/schema-info")
def governance_schema_info(user: dict[str, Any] = Depends(require_roles("admin", "analyst"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="gov_schema_info").inc()
    with get_db() as db:
        row = db.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
    return {"schema_version": int(row["value"]) if row else None}


@gov_router.get("/fusion-policy")
def governance_fusion_policy(
    user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer")),
    profile: str | None = Query(None, description="balanced or high_recall; default from effective settings"),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="gov_fusion_policy").inc()
    prof = profile
    if not prof or not str(prof).strip():
        with get_db() as db:
            eff, _ = effective_for_user(db, user)
        prof = str(eff.get("active_unsw_profile") or "balanced")
    if prof not in ("balanced", "high_recall"):
        raise HTTPException(status_code=400, detail="profile must be balanced or high_recall")
    return fusion_policy_snapshot(profile=prof)


@gov_router.get("/drift-report")
def governance_drift_report(user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="gov_drift_report").inc()
    p = project_root() / "reports" / "drift_report.json"
    if not p.is_file():
        raise HTTPException(
            status_code=404,
            detail="no drift report; run scripts/run_drift_report.py or compare_feature_stats with --out-json",
        )
    return json.loads(p.read_text(encoding="utf-8"))


@int_router.post("/webhook/test")
def integration_webhook_test(payload: dict[str, Any], user: dict[str, Any] = Depends(require_roles("admin", "analyst"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="integration_webhook_test").inc()
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="url is required")
    req = urllib.request.Request(
        str(url),
        data=json.dumps(payload.get("payload", {"msg": "hawk-eye test"})).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            code = int(r.status)
    except urllib.error.URLError as e:
        raise HTTPException(status_code=400, detail=f"webhook failed: {e}") from e
    _audit(user["username"], "integration.webhook_test", {"status_code": code}, tenant_id=user.get("tenant_id"))
    return {"ok": True, "status_code": code}


@rule_router.post("")
def create_rule(req: RuleCreate, user: dict[str, Any] = Depends(require_roles("admin", "analyst"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="rule_create").inc()
    try:
        tid = tenant_id_for_write(user, req.tenant_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO detection_rules(name, enabled, severity, expression, created_at, tenant_id) VALUES(?, ?, ?, ?, ?, ?)",
            (req.name, 1 if req.enabled else 0, req.severity, req.expression, _ts(), tid),
        )
    _audit(user["username"], "rule.create", {"name": req.name}, tenant_id=tid)
    return {"ok": True, "rule_id": int(cur.lastrowid)}


@rule_router.get("")
def list_rules(user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="rule_list").inc()
    extra, params = sql_tenant_and(user, "detection_rules")
    with get_db() as db:
        rows = db.execute("SELECT * FROM detection_rules WHERE 1=1" + extra + " ORDER BY id DESC", params).fetchall()
    return {"rows": [dict(r) for r in rows]}


@suppression_router.post("")
def create_suppression(
    req: SuppressionCreate,
    user: dict[str, Any] = Depends(require_roles("admin", "analyst")),
) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="suppression_create").inc()
    try:
        tid = tenant_id_for_write(user, req.tenant_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO suppressions(target_type, target_value, reason, until_ts, created_at, tenant_id) VALUES(?, ?, ?, ?, ?, ?)",
            (req.target_type, req.target_value, req.reason, req.until_ts, _ts(), tid),
        )
    _audit(
        user["username"],
        "suppression.create",
        {"target_type": req.target_type, "target_value": req.target_value},
        tenant_id=tid,
    )
    return {"ok": True, "suppression_id": int(cur.lastrowid)}


@suppression_router.get("")
def list_suppressions(user: dict[str, Any] = Depends(require_roles("admin", "analyst", "viewer"))) -> dict[str, Any]:
    REQ_COUNTER.labels(endpoint="suppression_list").inc()
    extra, params = sql_tenant_and(user, "suppressions")
    with get_db() as db:
        rows = db.execute("SELECT * FROM suppressions WHERE 1=1" + extra + " ORDER BY id DESC", params).fetchall()
    return {"rows": [dict(r) for r in rows]}


@ws_router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket, token: str | None = None) -> None:
    if not token:
        await websocket.close(code=4401)
        return
    with get_db() as db:
        row = db.execute(
            """
            SELECT u.id, u.username, u.role, u.tenant_id, t.expires_at, t.revoked
            FROM auth_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token = ?
            """,
            (token,),
        ).fetchone()
    if not row or int(row["revoked"]) == 1 or int(row["expires_at"]) <= _ts():
        await websocket.close(code=4401)
        return
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
