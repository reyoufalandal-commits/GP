from __future__ import annotations

from pathlib import Path

import pandas as pd

from hawk_eye.bundle import load as load_bundle
from hawk_eye.bundle import save as save_bundle
from hawk_eye.score import score_dataframe
from hawk_eye.train import _build_pipeline


def test_bundle_smoke_train_save_load_score(tmp_path: Path) -> None:
    X = pd.read_csv(Path("tests/fixtures/sample_features.csv"))
    y = pd.read_csv(Path("tests/fixtures/sample_labels.csv"))["label"].to_numpy()

    pipe = _build_pipeline(list(X.columns), logistic_class_weight=None)
    pipe.fit(X, y)

    bundle_dir = tmp_path / "hawk-eye-test-bundle"
    save_bundle(
        bundle_dir=bundle_dir,
        model=pipe.named_steps["model"],
        preprocessor=pipe.named_steps["preprocessor"],
        feature_columns=list(X.columns),
        config={"bundle_version": "test"},
        metadata={"fixture": True},
    )

    bundle = load_bundle(bundle_dir)
    assert bundle.feature_columns == list(X.columns)

    out = score_dataframe(X, bundle_dir=bundle_dir)
    assert len(out) == len(X)
    assert "model_version" in out.columns
    assert out["model_version"].iloc[0] == "test"


def test_bundle_smoke_hist_gradient_boosting(tmp_path: Path) -> None:
    X = pd.read_csv(Path("tests/fixtures/sample_features.csv"))
    y = pd.read_csv(Path("tests/fixtures/sample_labels.csv"))["label"].to_numpy()

    pipe = _build_pipeline(
        list(X.columns),
        logistic_class_weight=None,
        model_type="hist_gradient_boosting",
    )
    pipe.fit(X, y)

    bundle_dir = tmp_path / "hawk-eye-hgb"
    save_bundle(
        bundle_dir=bundle_dir,
        model=pipe.named_steps["model"],
        preprocessor=pipe.named_steps["preprocessor"],
        feature_columns=list(X.columns),
        config={"bundle_version": "test-hgb"},
        metadata={"fixture": True},
    )

    out = score_dataframe(X, bundle_dir=bundle_dir)
    assert len(out) == len(X)

