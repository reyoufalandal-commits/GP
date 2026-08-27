from __future__ import annotations

import hashlib
import time
import uuid

from fastapi.testclient import TestClient

from hawk_eye.api_service import app
from hawk_eye.backend.db import get_db, init_db


def test_viewer_forbidden_on_tenant_create() -> None:
    init_db()
    uname = f"viewer_{uuid.uuid4().hex[:8]}"
    with get_db() as db:
        db.execute(
            "INSERT INTO users(username, password_hash, role, tenant_id, created_at) VALUES(?, ?, ?, ?, ?)",
            (uname, hashlib.sha256("pw123".encode("utf-8")).hexdigest(), "viewer", None, int(time.time())),
        )
    c = TestClient(app)
    login = c.post("/api/v1/auth/login", json={"username": uname, "password": "pw123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    r = c.post("/api/v1/tenants", json={"name": "forbidden-tenant"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
