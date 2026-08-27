from __future__ import annotations

import pandas as pd


def test_fixture_label_contract_exists() -> None:
    y = pd.read_csv("tests/fixtures/sample_labels.csv")
    assert "label" in y.columns
    assert y["label"].notna().all()


def test_fixture_feature_contract_non_empty() -> None:
    x = pd.read_csv("tests/fixtures/sample_features.csv")
    assert len(x.columns) >= 4
    assert len(x) > 0

