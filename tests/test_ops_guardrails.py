from __future__ import annotations

from pathlib import Path

import pandas as pd

from hawk_eye.ops_guardrails import summarize_operational_health


def test_operational_health_summary(tmp_path: Path) -> None:
    p = tmp_path / "triage.parquet"
    pd.DataFrame({"decision_label": ["KnownAttack", "AttackUncertain", "BenignOrLowRisk"]}).to_parquet(
        p, index=False
    )
    out = summarize_operational_health(p, max_attack_uncertain_rate=0.5)
    assert out["healthy"] is True
    assert out["rows"] == 3
