from __future__ import annotations

from fastapi.testclient import TestClient

from hawk_eye.api_service import app


def _admin_headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_score_accepts_zeek_conn_like_rows() -> None:
    """Rows shaped like Zeek conn fields are mapped to the bundle contract (same as triage-conn-log-file)."""
    c = TestClient(app)
    h = _admin_headers(c)
    rows = [
        {
            "proto": "tcp",
            "duration": "1.5",
            "orig_bytes": "100",
            "resp_bytes": "200",
            "orig_pkts": "2",
            "resp_pkts": "3",
        }
    ]
    r = c.post("/api/v1/detections/score", json={"rows": rows}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "rows" in body
    assert len(body["rows"]) >= 1


def test_score_rejects_unrecognized_columns() -> None:
    c = TestClient(app)
    h = _admin_headers(c)
    r = c.post("/api/v1/detections/score", json={"rows": [{"not_a_feature": 1}]}, headers=h)
    assert r.status_code == 400
    assert "contract" in r.json().get("detail", "").lower() or "zeek" in r.json().get("detail", "").lower()


def test_supervised_feature_schema_lists_columns() -> None:
    c = TestClient(app)
    h = _admin_headers(c)
    r = c.get("/api/v1/detections/supervised-feature-schema", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "feature_columns" in body and isinstance(body["feature_columns"], list)
    assert "n_features" in body and body["n_features"] == len(body["feature_columns"])
    assert "supervised_dir" in body
