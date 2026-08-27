from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from hawk_eye.api_service import app
from hawk_eye.bundle import save as save_bundle
from hawk_eye.labels_binary import to_benign_attack
from hawk_eye.train import _build_pipeline


def _admin_headers(c: TestClient) -> dict[str, str]:
    login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_explain_row_from_bundle(tmp_path_factory) -> None:
    tmp = tmp_path_factory.mktemp("sup")
    X = pd.read_csv(Path("tests/fixtures/sample_features.csv"))
    y = pd.read_csv(Path("tests/fixtures/sample_labels.csv"))["label"].to_numpy()
    yb = to_benign_attack(y, {"benign"})
    pipe = _build_pipeline(list(X.columns), model_type="logistic")
    pipe.fit(X, yb)
    save_bundle(
        bundle_dir=tmp,
        model=pipe.named_steps["model"],
        preprocessor=pipe.named_steps["preprocessor"],
        feature_columns=list(X.columns),
        config={"bundle_version": "test-explain", "binary_benign_vs_attack": True},
        metadata={},
    )

    c = TestClient(app)
    h = _admin_headers(c)
    row = X.iloc[0].to_dict()
    r = c.post(
        "/api/v1/detections/explain",
        json={"row": row, "supervised_dir": str(tmp), "row_index": 0, "top_k": 4},
        headers=h,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["supervised_dir"] == str(tmp)
    assert data["explain"]["model_version"] == "test-explain"
    assert data["explain"]["row_index"] == 0
    assert "top_features" in data["explain"]
    assert isinstance(data["explain"]["top_features"], list)


def test_llm_format_forced_stub() -> None:
    c = TestClient(app)
    h = _admin_headers(c)
    expl = {
        "model_version": "v",
        "row_index": 0,
        "top_features": [{"name": "f_bytes", "value": 1.0, "contribution": 0.5}],
    }
    r = c.post(
        "/api/v1/llm/format-explanation?use_llm=false",
        json={"explain": expl},
        headers=h,
    )
    assert r.status_code == 200
    out = r.json()
    assert out["source"] == "deterministic_stub"
    assert "offline stub" in out["text"] or "Summary" in out["text"]


def test_llm_format_mock_openai() -> None:
    c = TestClient(app)
    h = _admin_headers(c)
    expl = {"model_version": "v", "row_index": 0, "top_features": []}

    def fake_urlopen(_req, **_kwargs):
        class R:
            def read(self):
                return b'{"choices":[{"message":{"content":"Mock analyst summary."}}]}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return None

        return R()

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("hawk_eye.llm_format.urllib.request.urlopen", fake_urlopen):
            r = c.post(
                "/api/v1/llm/format-explanation?use_llm=true",
                json={"explain": expl},
                headers=h,
            )
    assert r.status_code == 200
    assert r.json()["source"] == "openai_compatible"
    assert "Mock analyst" in r.json()["text"]


def test_llm_capabilities_endpoint() -> None:
    c = TestClient(app)
    h = _admin_headers(c)
    r = c.get("/api/v1/llm/capabilities", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "llm_available" in body
    assert "provider" in body
    assert body["provider"] in ("none", "openai", "deepseek")
    assert "base_url_display" in body
    assert "model_default" in body
