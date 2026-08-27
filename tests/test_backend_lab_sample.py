from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hawk_eye.api_service import app

_REPO = Path(__file__).resolve().parents[1]


def _admin_headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_lab_sample_rows_endpoint() -> None:
    c = TestClient(app)
    h = _admin_headers(c)
    r = c.get("/api/v1/detections/lab-sample-rows", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "rows" in data
    assert isinstance(data["rows"], list) and len(data["rows"]) >= 3
    first = data["rows"][0]
    assert "Protocol" in first
    assert "Flow Duration" in first
    third = data["rows"][2]
    assert third.get("Protocol") == 0.5235


@pytest.mark.skipif(not (_REPO / "artifacts" / "hawk-eye-binary").is_dir(), reason="minimal bundles not built")
def test_lab_sample_third_row_full_triage_zero_day_heuristic() -> None:
    """Third JSON row is tuned for CI minimal bundles: Suspected_ZeroDay + AttackUncertain."""
    c = TestClient(app)
    h = _admin_headers(c)
    raw = json.loads((_REPO / "data" / "lab" / "model_lab_sample_rows.json").read_text(encoding="utf-8"))
    r = c.post("/api/v1/detections/triage", json={"rows": raw}, headers=h)
    assert r.status_code == 200
    row = r.json()["rows"][2]
    assert row.get("prediction") == "Suspected_ZeroDay"
    assert row.get("decision_label") == "AttackUncertain"
    assert row.get("is_novel_flagged") is True
