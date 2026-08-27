from __future__ import annotations

from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def _headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_stream_incident_report_unknown_job() -> None:
    c = TestClient(app)
    h = _headers(c)
    r = c.post("/api/v1/llm/stream-incident-report", json={"job_id": 999999999}, headers=h)
    assert r.status_code == 404
