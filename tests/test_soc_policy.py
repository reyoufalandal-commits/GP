from __future__ import annotations

import pandas as pd

from hawk_eye.soc_policy import apply_soc_policy


def test_soc_policy_benign_allow_and_attack_paths() -> None:
    benign = frozenset({"BENIGN", "benign"})
    df = pd.DataFrame(
        {
            "prediction": ["BENIGN", "DoS", "DoS", "PortScan"],
            "proba_max": [0.99, 0.95, 0.4, float("nan")],
        }
    )
    out = apply_soc_policy(df, benign_labels=benign, block_min_proba=0.92)
    assert list(out["soc_action"]) == ["allow", "block_candidate", "alert_review", "alert_review"]
    assert out.loc[0, "soc_reason"] == "benign_prediction"
    assert "attack_high_confidence" in out.loc[1, "soc_reason"]
    assert "attack_low_confidence" in out.loc[2, "soc_reason"]
    assert "missing_or_invalid_proba" in out.loc[3, "soc_reason"]


def test_soc_policy_anomaly_escalate_benign() -> None:
    benign = frozenset({"benign"})
    df = pd.DataFrame(
        {
            "prediction": ["benign", "benign"],
            "anomaly_score": [0.1, 99.0],
        }
    )
    out = apply_soc_policy(
        df,
        benign_labels=benign,
        pred_col="prediction",
        proba_col="proba_max",
        anomaly_col="anomaly_score",
        anomaly_benign_escalate=5.0,
    )
    assert out.loc[0, "soc_action"] == "allow"
    assert out.loc[1, "soc_action"] == "alert_review"
    assert "high_anomaly_score" in out.loc[1, "soc_reason"]
