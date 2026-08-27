from __future__ import annotations

from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def test_backend_health_and_summary() -> None:
    c = TestClient(app)
    h = c.get("/health")
    assert h.status_code == 200
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    r = c.get("/api/v1/reports/summary", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "alerts_total" in data
    assert "cases_total" in data
