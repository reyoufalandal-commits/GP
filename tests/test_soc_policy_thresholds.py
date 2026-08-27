from __future__ import annotations

import pandas as pd

from hawk_eye.soc_policy import apply_soc_policy


def test_soc_policy_block_min_boundary() -> None:
    df = pd.DataFrame(
        {
            "prediction": ["X"],
            "proba_max": [0.6],
        }
    )
    low = apply_soc_policy(df, benign_labels=frozenset({"B"}), block_min_proba=0.99)
    high = apply_soc_policy(df, benign_labels=frozenset({"B"}), block_min_proba=0.5)
    assert low.loc[0, "soc_action"] == "alert_review"
    assert high.loc[0, "soc_action"] == "block_candidate"
