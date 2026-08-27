from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from hawk_eye.bundle import load as load_bundle
from hawk_eye.bundle import save as save_bundle
from hawk_eye.labels_binary import to_benign_attack
from hawk_eye.train import _build_pipeline


def test_binary_labels_mapping() -> None:
    X = pd.read_csv(Path("tests/fixtures/sample_features.csv"))
    y = pd.read_csv(Path("tests/fixtures/sample_labels.csv"))["label"].to_numpy()
    yb = to_benign_attack(y, {"benign"})
    assert set(np.unique(yb)) <= {"Benign", "Attack"}


def test_binary_bundle_scores_attack_column(tmp_path: Path) -> None:
    X = pd.read_csv(Path("tests/fixtures/sample_features.csv"))
    y = pd.read_csv(Path("tests/fixtures/sample_labels.csv"))["label"].to_numpy()
    yb = to_benign_attack(y, {"benign"})
    pipe = _build_pipeline(list(X.columns), model_type="logistic")
    pipe.fit(X, yb)

    bundle_dir = tmp_path / "bin"
    save_bundle(
        bundle_dir=bundle_dir,
        model=pipe.named_steps["model"],
        preprocessor=pipe.named_steps["preprocessor"],
        feature_columns=list(X.columns),
        config={"bundle_version": "t", "binary_benign_vs_attack": True},
        metadata={},
    )
    b = load_bundle(bundle_dir)
    from hawk_eye.score import build_score_dataframe

    out = build_score_dataframe(X, bundle_dir=bundle_dir)
    assert "p_attack" in out.columns or "score" in out.columns
    assert (out["score"] >= 0).all() and (out["score"] <= 1).all()
