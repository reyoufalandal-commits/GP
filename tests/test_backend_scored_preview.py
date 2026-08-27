from __future__ import annotations

import json
import time

import pandas as pd
from fastapi.testclient import TestClient

from hawk_eye.api_service import app
from hawk_eye.backend.db import db_path, get_db


def _admin_headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_scored_preview_returns_tail_rows() -> None:
    root = db_path().resolve().parents[2]
    sess = root / "data" / "stream_sessions"
    sess.mkdir(parents=True, exist_ok=True)
    parquet_p = sess / "job_888001_scored.parquet"
    pd.DataFrame(
        {"a": [1, 2, 3, 4, 5], "decision_label": ["X"] * 5},
    ).to_parquet(parquet_p, index=False)
    payload = {"output_path": str(parquet_p.resolve())}
    ts = int(time.time())
    try:
        with get_db() as db:
            db.execute(
                """INSERT INTO background_jobs(
                    tenant_id, job_type, payload_json, status, result_path, error, created_at, updated_at
                ) VALUES (NULL, 'stream_collect', ?, 'completed', NULL, NULL, ?, ?)""",
                (json.dumps(payload), ts, ts),
            )
            jid = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])

        c = TestClient(app)
        h = _admin_headers(c)
        r = c.get(f"/api/v1/jobs/{jid}/scored-preview?limit=2", headers=h)
        assert r.status_code == 200
        data = r.json()
        assert data["total_rows"] == 5
        assert data["returned"] == 2
        assert len(data["rows"]) == 2
        assert data["rows"][-1]["a"] == 5

        with get_db() as db:
            db.execute("DELETE FROM background_jobs WHERE id = ?", (jid,))
    finally:
        parquet_p.unlink(missing_ok=True)
