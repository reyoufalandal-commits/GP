from __future__ import annotations

from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def test_ready_endpoint_has_expected_shape() -> None:
    c = TestClient(app)
    r = c.get("/ready")
    assert r.status_code == 200
    data = r.json()
    assert "ready" in data
    assert "checks" in data
    assert "binary_dir" in data["checks"]

