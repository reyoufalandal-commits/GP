from __future__ import annotations

from pathlib import Path

import pandas as pd

from hawk_eye.bundle import save as save_bundle
from hawk_eye.score import build_score_dataframe
from hawk_eye.train import _build_pipeline


def test_build_score_predictions_and_proba_all(tmp_path: Path) -> None:
    X = pd.read_csv(Path("tests/fixtures/sample_features.csv"))
    y = pd.read_csv(Path("tests/fixtures/sample_labels.csv"))["label"].to_numpy()

    pipe = _build_pipeline(list(X.columns), logistic_class_weight=None)
    pipe.fit(X, y)

    bundle_dir = tmp_path / "bundle"
    save_bundle(
        bundle_dir=bundle_dir,
        model=pipe.named_steps["model"],
        preprocessor=pipe.named_steps["preprocessor"],
        feature_columns=list(X.columns),
        config={"bundle_version": "test-score"},
        metadata={},
    )

    out = build_score_dataframe(
        X,
        bundle_dir=bundle_dir,
        predictions=True,
        proba_all=True,
        proba_max=True,
    )
    assert "prediction" in out.columns
    assert "proba_max" in out.columns
    assert "score" in out.columns
    assert "model_version" in out.columns
    assert len(out) == len(X)
    # binary: p_benign, p_attack style from classes_
    p_cols = [c for c in out.columns if c.startswith("p_")]
    assert len(p_cols) >= 2
