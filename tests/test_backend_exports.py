from __future__ import annotations

from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def _admin_headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_export_alerts_csv_authenticated() -> None:
    c = TestClient(app)
    h = _admin_headers(c)
    r = c.get("/api/v1/export/alerts.csv", headers=h)
    assert r.status_code == 200
    assert "text/csv" in (r.headers.get("content-type") or "")


def test_export_audit_json_authenticated() -> None:
    c = TestClient(app)
    h = _admin_headers(c)
    r = c.get("/api/v1/export/audit.json", headers=h)
    assert r.status_code == 200
    ct = r.headers.get("content-type") or ""
    assert "json" in ct or "octet-stream" in ct


def test_export_alerts_csv_unauthorized() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/export/alerts.csv")
    assert r.status_code == 401
