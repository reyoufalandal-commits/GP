from __future__ import annotations

import pandas as pd

from hawk_eye.decision_fusion import KNOWN_ATTACK
from hawk_eye.live.dual_mode import (
    known_attack_type_counts,
    prepare_input_dataframe,
    read_zeek_conn_log_with_fields,
    summarize_stream_risk,
)


def test_read_zeek_conn_log_with_fields(tmp_path) -> None:
    p = tmp_path / "conn.log"
    p.write_text(
        "#fields\tts\tuid\tproto\tduration\torig_bytes\tresp_bytes\torig_pkts\tresp_pkts\n"
        "1.0\tC1\ttcp\t1.5\t100\t200\t2\t3\n"
    )
    df = read_zeek_conn_log_with_fields(p)
    assert "proto" in df.columns
    assert len(df) == 1


def test_summarize_stream_risk_low_and_elevated() -> None:
    low = summarize_stream_risk(
        rows_scored=10,
        decision_counts={"BenignOrLowRisk": 10},
        known_attack_types={},
    )
    assert low["risk_level"] == "low"
    assert low["attack_indicators"] == "none"
    el = summarize_stream_risk(
        rows_scored=3,
        decision_counts={"KnownAttack": 1, "AttackUncertain": 1, "BenignOrLowRisk": 1},
        known_attack_types={"DoS": 1},
    )
    assert el["risk_level"] == "elevated"
    assert el["attack_indicators"] == "present"


def test_known_attack_type_counts_uses_supervised_prediction() -> None:
    df = pd.DataFrame(
        {
            "decision_label": [KNOWN_ATTACK, KNOWN_ATTACK, "BenignOrLowRisk"],
            "supervised_prediction": ["DoS", "Analysis", "Benign"],
        }
    )
    assert known_attack_type_counts(df) == {"DoS": 1, "Analysis": 1}


def test_prepare_input_dataframe_zeek_mapping() -> None:
    raw = pd.DataFrame(
        {
            "proto": ["tcp"],
            "duration": [2.0],
            "orig_bytes": [120.0],
            "resp_bytes": [80.0],
            "orig_pkts": [3.0],
            "resp_pkts": [2.0],
            "id.orig_p": [44444],
            "id.resp_p": [443],
        }
    )
    expected = [
        "Protocol",
        "Flow Duration",
        "Total Fwd Packets",
        "Total Backward Packets",
        "Flow Bytes/s",
        "Flow Packets/s",
    ]
    out = prepare_input_dataframe(raw, expected)
    assert set(expected).issubset(out.columns)
    assert float(out.loc[0, "Protocol"]) == 6.0
    assert float(out.loc[0, "Flow Duration"]) > 0

