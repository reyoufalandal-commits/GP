from __future__ import annotations

from pathlib import Path

import pandas as pd

from hawk_eye.drift_compare import compare_numeric_drift


def test_compare_numeric_drift_basic(tmp_path: Path) -> None:
    ref = tmp_path / "ref.csv"
    smp = tmp_path / "smp.csv"
    pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]}).to_csv(ref, index=False)
    pd.DataFrame({"a": [10.0, 20.0], "b": [3.0, 4.0]}).to_csv(smp, index=False)
    rows = compare_numeric_drift(ref, smp)
    assert len(rows) >= 1
    assert rows[0]["column"] == "a"
