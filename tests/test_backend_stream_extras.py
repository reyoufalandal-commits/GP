from __future__ import annotations

from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def _headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_compare_streams_not_found() -> None:
    c = TestClient(app)
    h = _headers(c)
    r = c.get("/api/v1/jobs/compare-streams?job_a=999999991&job_b=999999992", headers=h)
    assert r.status_code == 404


def test_report_summary_includes_last_stream_key() -> None:
    c = TestClient(app)
    h = _headers(c)
    r = c.get("/api/v1/reports/summary", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "last_stream_job" in data
