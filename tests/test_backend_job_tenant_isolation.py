from __future__ import annotations

import hashlib
import time
import uuid

from fastapi.testclient import TestClient

from hawk_eye.api_service import app
from hawk_eye.backend.db import get_db, init_db


def test_get_job_returns_404_for_other_tenant() -> None:
    init_db()
    ts = int(time.time())
    uid = uuid.uuid4().hex[:10]
    uname_a = f"iso_a_{uid}"
    uname_b = f"iso_b_{uid}"
    tname_a = f"t_a_{uid}"
    tname_b = f"t_b_{uid}"
    pw_hash = hashlib.sha256("pw123456".encode("utf-8")).hexdigest()

    with get_db() as db:
        db.execute("INSERT INTO tenants(name, created_at) VALUES(?, ?)", (tname_a, ts))
        tid_a = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        db.execute("INSERT INTO tenants(name, created_at) VALUES(?, ?)", (tname_b, ts))
        tid_b = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        db.execute(
            "INSERT INTO users(username, password_hash, role, tenant_id, created_at) VALUES(?, ?, ?, ?, ?)",
            (uname_a, pw_hash, "viewer", tid_a, ts),
        )
        db.execute(
            "INSERT INTO users(username, password_hash, role, tenant_id, created_at) VALUES(?, ?, ?, ?, ?)",
            (uname_b, pw_hash, "viewer", tid_b, ts),
        )
        db.execute(
            """INSERT INTO background_jobs(
                tenant_id, job_type, payload_json, status, result_path, error, created_at, updated_at
            ) VALUES (?, 'export_alerts_csv', '{}', 'pending', NULL, NULL, ?, ?)""",
            (tid_a, ts, ts),
        )
        jid = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

    try:
        c = TestClient(app)
        tok_b = c.post("/api/v1/auth/login", json={"username": uname_b, "password": "pw123456"}).json()["access_token"]
        r_denied = c.get(f"/api/v1/jobs/{jid}", headers={"Authorization": f"Bearer {tok_b}"})
        assert r_denied.status_code == 404

        tok_a = c.post("/api/v1/auth/login", json={"username": uname_a, "password": "pw123456"}).json()["access_token"]
        r_ok = c.get(f"/api/v1/jobs/{jid}", headers={"Authorization": f"Bearer {tok_a}"})
        assert r_ok.status_code == 200
        assert r_ok.json()["job"]["id"] == jid
    finally:
        with get_db() as db:
            db.execute("DELETE FROM background_jobs WHERE id = ?", (jid,))
            db.execute("DELETE FROM users WHERE username IN (?, ?)", (uname_a, uname_b))
            db.execute("DELETE FROM tenants WHERE id IN (?, ?)", (tid_a, tid_b))
