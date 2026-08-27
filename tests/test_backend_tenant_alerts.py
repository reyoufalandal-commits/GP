from __future__ import annotations

import hashlib
import json
import time
import uuid

from fastapi.testclient import TestClient

from hawk_eye.api_service import app
from hawk_eye.backend.db import get_db, init_db


def test_list_alerts_excludes_other_tenant() -> None:
    init_db()
    ts = int(time.time())
    uid = uuid.uuid4().hex[:10]
    uname_a = f"al_a_{uid}"
    uname_b = f"al_b_{uid}"
    tname_a = f"ta_{uid}"
    tname_b = f"tb_{uid}"
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
            """INSERT INTO alerts(
                tenant_id, severity, title, decision_label, payload_json, status, suppressed, created_at
            ) VALUES (?, ?, ?, ?, ?, 'new', 0, ?)""",
            (
                tid_a,
                "high",
                "tenant-a-alert",
                "KnownAttack",
                json.dumps({"k": "v"}),
                ts,
            ),
        )
        aid = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

    try:
        c = TestClient(app)
        tok_b = c.post("/api/v1/auth/login", json={"username": uname_b, "password": "pw123456"}).json()["access_token"]
        r = c.get("/api/v1/alerts", headers={"Authorization": f"Bearer {tok_b}"})
        assert r.status_code == 200
        ids = [row["id"] for row in r.json().get("rows", [])]
        assert aid not in ids

        tok_a = c.post("/api/v1/auth/login", json={"username": uname_a, "password": "pw123456"}).json()["access_token"]
        r2 = c.get("/api/v1/alerts", headers={"Authorization": f"Bearer {tok_a}"})
        assert r2.status_code == 200
        ids_a = [row["id"] for row in r2.json().get("rows", [])]
        assert aid in ids_a
    finally:
        with get_db() as db:
            db.execute("DELETE FROM alerts WHERE id = ?", (aid,))
            db.execute("DELETE FROM users WHERE username IN (?, ?)", (uname_a, uname_b))
            db.execute("DELETE FROM tenants WHERE id IN (?, ?)", (tid_a, tid_b))
