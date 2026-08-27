from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def _admin_headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_alert_case_rule_suppression_workflow() -> None:
    c = TestClient(app)
    h = _admin_headers(c)

    a = c.post(
        "/api/v1/alerts",
        json={"title": "test alert", "severity": "high", "decision_label": "AttackUncertain", "payload": {"ip": "1.1.1.1"}},
        headers=h,
    )
    assert a.status_code == 200
    alert_id = a.json()["alert_id"]

    s = c.patch(f"/api/v1/alerts/{alert_id}/status", json={"status": "acknowledged"}, headers=h)
    assert s.status_code == 200
    assert s.json()["row"]["status"] == "acknowledged"

    case = c.post("/api/v1/cases", json={"title": "case-1", "priority": "high", "alert_id": alert_id}, headers=h)
    assert case.status_code == 200
    case_id = case.json()["case_id"]

    cm = c.post(f"/api/v1/cases/{case_id}/comments", json={"comment": "investigating"}, headers=h)
    assert cm.status_code == 200
    assert c.get(f"/api/v1/cases/{case_id}/comments", headers=h).status_code == 200

    ca = c.post(f"/api/v1/cases/{case_id}/assign", json={"assignee": "analyst1"}, headers=h)
    assert ca.status_code == 200
    assert c.get(f"/api/v1/cases/{case_id}/assignments", headers=h).status_code == 200

    rule_name = f"rule-test-{uuid.uuid4().hex[:12]}"
    r = c.post("/api/v1/rules", json={"name": rule_name, "expression": "p_attack > 0.9"}, headers=h)
    assert r.status_code == 200
    assert c.get("/api/v1/rules", headers=h).status_code == 200

    sup = c.post(
        "/api/v1/suppressions",
        json={"target_type": "ip", "target_value": "1.1.1.1", "reason": "maintenance"},
        headers=h,
    )
    assert sup.status_code == 200
    assert c.get("/api/v1/suppressions", headers=h).status_code == 200
