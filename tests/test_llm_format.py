from __future__ import annotations

import json
from unittest.mock import patch

from hawk_eye.llm_format import (
    explain_payload_to_stub_text,
    format_model_explanation,
    format_stream_incident_report,
    grounded_facts_for_stream_session,
    load_explain_prompt,
    redact_sample_rows_for_llm,
)


def test_stub_text_includes_features() -> None:
    payload = {
        "model_version": "t",
        "row_index": 0,
        "top_features": [{"name": "Flow Duration", "value": 1.0, "contribution": 0.25}],
    }
    s = explain_payload_to_stub_text(payload)
    assert "Flow Duration" in s
    assert "0.2500" in s or "0.25" in s


def test_format_without_key_is_stub() -> None:
    out = format_model_explanation({"row_index": 1, "top_features": []}, use_llm=False)
    assert out["source"] == "deterministic_stub"
    assert "offline stub" in out["text"].lower() or "Row index" in out["text"]


def test_format_with_empty_key_env_is_stub(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    out = format_model_explanation({"top_features": []}, use_llm=None)
    assert out["source"] == "deterministic_stub"


def test_redact_ips_in_sample_rows() -> None:
    rows = [{"id.orig_h": "192.168.1.10", "x": 1}]
    out = redact_sample_rows_for_llm(rows)
    assert out[0]["id.orig_h"] == "[redacted-ip]"
    assert out[0]["x"] == 1


def test_load_explain_prompt_non_empty() -> None:
    p = load_explain_prompt()
    assert "analyst" in p.lower() or "security" in p.lower() or "feature" in p.lower()


def test_grounded_facts_for_stream_session() -> None:
    s = {
        "mode": "stream_window",
        "duration_seconds": 120.0,
        "rows_scored": 10,
        "decision_counts": {"BenignOrLowRisk": 8, "KnownAttack": 2},
        "known_attack_types": {"dns_tunnel": 2},
        "risk_level": "elevated",
    }
    g = grounded_facts_for_stream_session(s)
    assert g["rows_scored"] == 10
    assert g["decision_counts"]["KnownAttack"] == 2
    assert g["known_attack_types"]["dns_tunnel"] == 2
    assert g["risk_level"] == "elevated"
    assert g.get("danger_verdict_hint") == "potential_danger_review_recommended"
    assert "plain_language_danger_hint" in g


def test_stream_incident_sorts_rows_by_signal() -> None:
    fake = {"choices": [{"message": {"content": "ok"}}]}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return json.dumps(fake).encode("utf-8")

    captured: list[bytes] = []

    def fake_urlopen(req, timeout=120):
        captured.append(req.data)
        return _Resp()

    summary = {
        "rows_scored": 3,
        "decision_counts": {"BenignOrLowRisk": 1, "KnownAttack": 1, "AttackUncertain": 1},
        "risk_level": "elevated",
        "risk_headline": "x",
        "risk_plain_summary": "y",
        "known_attack_types": {},
    }
    rows = [
        {"decision_label": "BenignOrLowRisk", "p_attack": 0.1},
        {"decision_label": "KnownAttack", "p_attack": 0.99, "supervised_prediction": "dns_tunnel"},
        {"decision_label": "AttackUncertain", "p_attack": 0.5},
    ]
    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("hawk_eye.llm_format.urllib.request.urlopen", fake_urlopen):
            format_stream_incident_report(summary, rows, use_llm=True, api_key="sk-test")
    assert captured, "urlopen should have been called"
    body = json.loads(captured[0].decode("utf-8"))
    user_obj = json.loads(body["messages"][1]["content"])
    assert "grounded_facts" in user_obj
    assert user_obj["grounded_facts"]["rows_scored"] == 3
    assert user_obj["sample_rows"][0]["decision_label"] == "KnownAttack"
    assert user_obj["sample_rows"][-1]["decision_label"] == "BenignOrLowRisk"


def test_stream_incident_stub() -> None:
    summary = {
        "rows_scored": 3,
        "decision_counts": {"BenignOrLowRisk": 2, "AttackUncertain": 1},
        "risk_level": "elevated",
        "attack_indicators": "present",
        "risk_headline": "Test headline",
        "risk_plain_summary": "Test summary",
        "known_attack_types": {},
    }
    rows = [{"decision_label": "AttackUncertain", "p_attack": 0.8}]
    out = format_stream_incident_report(summary, rows, use_llm=False)
    assert out["source"] == "deterministic_stub"
    text = out["text"].lower()
    assert "danger" in text or "risk_level" in text
    assert "test headline" in text


def test_format_with_mocked_openai() -> None:
    fake = {
        "choices": [{"message": {"content": "Mocked analyst summary: elevated flow duration."}}]
    }
    payload = {"row_index": 0, "top_features": [{"name": "x", "value": 1.0, "contribution": 0.1}]}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return json.dumps(fake).encode("utf-8")

    def fake_urlopen(req, timeout=120):
        return _Resp()

    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
        with patch("hawk_eye.llm_format.urllib.request.urlopen", fake_urlopen):
            out = format_model_explanation(payload, use_llm=True, api_key="sk-test")

    assert out["source"] == "openai_compatible"
    assert "Mocked analyst" in out["text"]


def test_format_with_deepseek_key_only_mocked(monkeypatch) -> None:
    fake = {
        "choices": [{"message": {"content": "Deepseek path OK."}}]
    }
    payload = {"row_index": 0, "top_features": [{"name": "x", "value": 1.0, "contribution": 0.1}]}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def read(self):
            return json.dumps(fake).encode("utf-8")

    def fake_urlopen(req, timeout=120):
        return _Resp()

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "sk-deepseek-test"}):
        with patch("hawk_eye.llm_format.urllib.request.urlopen", fake_urlopen):
            out = format_model_explanation(payload, use_llm=True)

    assert out["source"] == "openai_compatible"
    assert "Deepseek path OK." in out["text"]
