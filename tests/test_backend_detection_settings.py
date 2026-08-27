from __future__ import annotations

from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def _admin_token(c: TestClient) -> str:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    return str(login.json()["access_token"])


def test_settings_detection_get() -> None:
    c = TestClient(app)
    token = _admin_token(c)
    r = c.get("/api/v1/settings/detection", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["active_dual_mode"] in ("stream", "batch")
    assert data["active_unsw_profile"] in ("balanced", "high_recall")
    assert "effective_artifact_dirs" in data
    assert "fusion_defaults_preview" in data


def test_settings_detection_patch_roundtrip() -> None:
    c = TestClient(app)
    token = _admin_token(c)
    h = {"Authorization": f"Bearer {token}"}
    before = c.get("/api/v1/settings/detection", headers=h).json()
    r = c.patch("/api/v1/settings/detection", json={"active_unsw_profile": "high_recall", "active_dual_mode": "stream"}, headers=h)
    assert r.status_code == 200
    got = c.get("/api/v1/settings/detection", headers=h).json()
    assert got["active_unsw_profile"] == "high_recall"
    assert got["active_dual_mode"] == "stream"
    c.patch(
        "/api/v1/settings/detection",
        json={"active_unsw_profile": before["active_unsw_profile"], "active_dual_mode": before["active_dual_mode"]},
        headers=h,
    )
