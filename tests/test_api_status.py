from __future__ import annotations

from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def test_api_v1_status_shape() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/status")
    assert r.status_code == 200
    data = r.json()
    assert data.get("service") == "hawk-eye-backend"
    assert "version" in data and isinstance(data["version"], str) and data["version"]
    assert "ready" in data
    assert "checks" in data
    llm = data.get("llm") or {}
    assert "llm_available" in llm
    assert "provider" in llm
    assert "model_default" in llm
