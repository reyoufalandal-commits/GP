from __future__ import annotations

from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def _headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _assert_history_shape(data: dict) -> None:
    assert "stream_jobs" in data
    assert "detection_runs" in data
    assert "scored_events_recent" in data
    assert isinstance(data["stream_jobs"], list)
    assert isinstance(data["detection_runs"], list)
    assert isinstance(data["scored_events_recent"], list)


def test_reports_detection_history_endpoint_shape() -> None:
    c = TestClient(app)
    h = _headers(c)
    r = c.get("/api/v1/reports/detection-history", headers=h)
    assert r.status_code == 200
    _assert_history_shape(r.json())


def test_detections_history_endpoint_alias() -> None:
    c = TestClient(app)
    h = _headers(c)
    r = c.get("/api/v1/detections/history", headers=h)
    assert r.status_code == 200
    _assert_history_shape(r.json())


def test_settings_detection_history_endpoint_alias() -> None:
    c = TestClient(app)
    h = _headers(c)
    r = c.get("/api/v1/settings/detection-history", headers=h)
    assert r.status_code == 200
    _assert_history_shape(r.json())


def test_top_level_detection_history_endpoint() -> None:
    c = TestClient(app)
    h = _headers(c)
    r = c.get("/api/v1/detection-history", headers=h)
    assert r.status_code == 200
    _assert_history_shape(r.json())
