from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from hawk_eye.api_service import app
from hawk_eye.backend.db import db_path, get_db


def _admin_headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_stream_summary_completed_stream_job() -> None:
    root = db_path().resolve().parents[2]
    sess = root / "data" / "stream_sessions"
    sess.mkdir(parents=True, exist_ok=True)
    summary_p = sess / "job_999001_summary.json"
    summary_p.write_text(
        json.dumps({"mode": "stream_window", "rows_scored": 3, "decision_counts": {"BenignOrLowRisk": 3}}),
        encoding="utf-8",
    )
    ts = int(time.time())
    try:
        with get_db() as db:
            db.execute(
                """INSERT INTO background_jobs(
                    tenant_id, job_type, payload_json, status, result_path, error, created_at, updated_at
                ) VALUES (NULL, 'stream_collect', '{}', 'completed', ?, NULL, ?, ?)""",
                (str(summary_p.resolve()), ts, ts),
            )
            jid = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

        c = TestClient(app)
        h = _admin_headers(c)
        r = c.get(f"/api/v1/jobs/{jid}/stream-summary", headers=h)
        assert r.status_code == 200
        assert r.json()["rows_scored"] == 3

        with get_db() as db:
            db.execute(
                """INSERT INTO background_jobs(
                    tenant_id, job_type, payload_json, status, result_path, error, created_at, updated_at
                ) VALUES (NULL, 'export_alerts_csv', '{}', 'completed', NULL, NULL, ?, ?)""",
                (ts, ts),
            )
            bad_id = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

        r2 = c.get(f"/api/v1/jobs/{bad_id}/stream-summary", headers=h)
        assert r2.status_code == 400
        assert "not a stream_collect" in r2.json()["detail"]

        with get_db() as db:
            db.execute("DELETE FROM background_jobs WHERE id IN (?, ?)", (jid, bad_id))
    finally:
        summary_p.unlink(missing_ok=True)


def test_stream_live_progress_running_and_completed() -> None:
    root = db_path().resolve().parents[2]
    sess = root / "data" / "stream_sessions"
    sess.mkdir(parents=True, exist_ok=True)
    progress_p = sess / "job_999003_progress.json"
    ts = int(time.time())
    progress_p.write_text(
        json.dumps({"rows_scored": 7, "conn_log_line_offset": 42, "updated_at": ts}),
        encoding="utf-8",
    )
    summary_p = sess / "job_999003_summary.json"
    summary_p.write_text(
        json.dumps({"mode": "stream_window", "rows_scored": 10, "decision_counts": {}}),
        encoding="utf-8",
    )
    payload_run = json.dumps({"progress_path": str(progress_p.resolve())})
    try:
        with get_db() as db:
            db.execute(
                """INSERT INTO background_jobs(
                    tenant_id, job_type, payload_json, status, result_path, error, created_at, updated_at
                ) VALUES (NULL, 'stream_collect', ?, 'running', NULL, NULL, ?, ?)""",
                (payload_run, ts, ts),
            )
            jid_run = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

        c = TestClient(app)
        h = _admin_headers(c)
        r = c.get(f"/api/v1/jobs/{jid_run}/stream-live-progress", headers=h)
        assert r.status_code == 200
        body = r.json()
        assert body["rows_scored"] == 7
        assert body["conn_log_line_offset"] == 42
        assert body["job_status"] == "running"

        with get_db() as db:
            db.execute(
                """INSERT INTO background_jobs(
                    tenant_id, job_type, payload_json, status, result_path, error, created_at, updated_at
                ) VALUES (NULL, 'stream_collect', '{}', 'completed', ?, NULL, ?, ?)""",
                (str(summary_p.resolve()), ts, ts),
            )
            jid_done = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

        r2 = c.get(f"/api/v1/jobs/{jid_done}/stream-live-progress", headers=h)
        assert r2.status_code == 200
        assert r2.json()["rows_scored"] == 10
        assert r2.json()["job_status"] == "completed"

        with get_db() as db:
            db.execute("DELETE FROM background_jobs WHERE id IN (?, ?)", (jid_run, jid_done))
    finally:
        progress_p.unlink(missing_ok=True)
        summary_p.unlink(missing_ok=True)
