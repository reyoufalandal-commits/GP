from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from hawk_eye.rag_triage import build_rag_index, explain_dataframe


def test_rag_build_and_explain(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        "\n".join(
            [
                json.dumps({"title": "Port Scan", "source": "x", "text": "many ports from one source"}),
                json.dumps({"title": "DDoS", "source": "y", "text": "burst traffic many sources one destination"}),
            ]
        )
    )
    idx = tmp_path / "rag.joblib"
    build_rag_index(corpus, idx)
    df = pd.DataFrame(
        [
            {
                "decision_label": "AttackUncertain",
                "reason_codes": "high_open_set_ood",
                "binary_prediction": "Attack",
                "suspected_zero_day_pct": 88.0,
            }
        ]
    )
    out = explain_dataframe(df, index_path=idx, only_uncertain=True)
    assert "llm_explanation_json" in out.columns
    assert out["llm_explanation_json"].iloc[0]
