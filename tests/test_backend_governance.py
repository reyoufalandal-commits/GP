from __future__ import annotations

from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def _headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_governance_fusion_policy() -> None:
    c = TestClient(app)
    h = _headers(c)
    r = c.get("/api/v1/governance/fusion-policy?profile=balanced", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "resolved_fusion_kwargs" in body
    assert "policy_composite_sha256" in body
    assert body["active_unsw_profile"] == "balanced"
