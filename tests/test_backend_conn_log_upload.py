from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def _admin_headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_triage_conn_log_file_requires_auth() -> None:
    c = TestClient(app)
    r = c.post(
        "/api/v1/detections/triage-conn-log-file",
        files={"file": ("x.log", b"#fields\tproto\n", "text/plain")},
    )
    assert r.status_code == 401


def test_triage_conn_log_file_happy_path(tmp_path: Path) -> None:
    log = tmp_path / "conn.log"
    log.write_text(
        "#fields\tts\tuid\tproto\tduration\torig_bytes\tresp_bytes\torig_pkts\tresp_pkts\n"
        "1.0\tC1\ttcp\t1.5\t100\t200\t2\t3\n",
        encoding="utf-8",
    )
    c = TestClient(app)
    h = _admin_headers(c)
    with log.open("rb") as f:
        r = c.post("/api/v1/detections/triage-conn-log-file", files={"file": ("conn.log", f, "text/plain")}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "rows" in body
    assert len(body["rows"]) >= 1
    assert body.get("source_filename") == "conn.log"


def test_triage_conn_log_file_empty_rejected(tmp_path: Path) -> None:
    log = tmp_path / "empty.log"
    log.write_text("", encoding="utf-8")
    c = TestClient(app)
    h = _admin_headers(c)
    with log.open("rb") as f:
        r = c.post("/api/v1/detections/triage-conn-log-file", files={"file": ("e.log", f, "text/plain")}, headers=h)
    assert r.status_code == 400
