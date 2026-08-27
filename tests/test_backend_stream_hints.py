from __future__ import annotations

from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def _admin_headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_stream_hints_ok() -> None:
    c = TestClient(app)
    h = _admin_headers(c)
    r = c.get("/api/v1/detections/stream-hints", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "repo_root" in data
    assert "live_conn_log_abs" in data
    assert "live_conn_log_exists" in data
    assert isinstance(data.get("zeek_in_path"), bool)
    assert "resolved_if_empty" in data
    assert "resolved_source" in data
    assert "live_conn_log_active_capture" in data
    assert isinstance(data.get("live_conn_log_active_capture"), bool)
    if data.get("live_conn_log_exists"):
        assert data.get("live_conn_log_age_sec") is None or isinstance(data.get("live_conn_log_age_sec"), (int, float))
