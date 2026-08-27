from __future__ import annotations

import pandas as pd

from hawk_eye.decision_fusion import ATTACK_UNCERTAIN, BENIGN_LOW_RISK, KNOWN_ATTACK, fuse_decisions


def test_fuse_decisions_labels_and_reasons() -> None:
    df = pd.DataFrame(
        {
            "binary_prediction": ["Attack", "Attack", "Benign", "Benign"],
            "p_attack": [0.93, 0.60, 0.20, 0.10],
            "is_attack_uncertain": [False, True, False, False],
            "is_novel_flagged": [False, True, False, False],
            "suspected_zero_day_pct": [10.0, 82.0, 15.0, 10.0],
            "open_set_ood_score": [0.10, 0.80, 0.20, 0.92],
        }
    )
    out = fuse_decisions(df)
    assert out["decision_label"].tolist() == [
        KNOWN_ATTACK,
        ATTACK_UNCERTAIN,
        BENIGN_LOW_RISK,
        ATTACK_UNCERTAIN,
    ]
    assert out["reason_codes"].str.len().gt(0).all()
