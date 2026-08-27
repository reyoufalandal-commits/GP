from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from hawk_eye.anomaly_bundle import save_anomaly_bundle
from hawk_eye.bundle import save as save_bundle
from hawk_eye.detect_novel import detect_novel_dataframe
from hawk_eye.train import _build_pipeline
from hawk_eye.train_anomaly import train_iforest


def test_detect_novel_assigns_novel_label_when_anomaly_and_uncertain(tmp_path: Path) -> None:
    X = pd.read_csv(Path("tests/fixtures/sample_features.csv"))
    y = pd.read_csv(Path("tests/fixtures/sample_labels.csv"))["label"].to_numpy()
    df = X.copy()
    df["label"] = y

    pipe = _build_pipeline(list(X.columns), logistic_class_weight=None)
    pipe.fit(X, y)

    sup_dir = tmp_path / "sup"
    save_bundle(
        bundle_dir=sup_dir,
        model=pipe.named_steps["model"],
        preprocessor=pipe.named_steps["preprocessor"],
        feature_columns=list(X.columns),
        config={"bundle_version": "t"},
        metadata={},
    )

    benign_only = df[df["label"] == "benign"].drop(columns=["label"])
    pre, clf = train_iforest(
        X_train=benign_only,
        feature_columns=list(X.columns),
        contamination=0.1,
    )
    Xt_b = pre.transform(benign_only)
    scores = -clf.score_samples(Xt_b)
    thr = float(np.percentile(scores, 95.0))

    anom_dir = tmp_path / "anom"
    save_anomaly_bundle(
        bundle_dir=anom_dir,
        preprocessor=pre,
        feature_columns=list(X.columns),
        config={
            "model_type": "isolation_forest",
            "threshold": thr,
            "bundle_version": "t",
        },
        sklearn_model=clf,
    )

    out = detect_novel_dataframe(
        df,
        supervised_dir=sup_dir,
        anomaly_dir=anom_dir,
        novel_label="Suspected_ZeroDay",
        confidence_threshold=0.99,
        require_low_confidence=True,
    )
    assert len(out) == len(df)
    assert out["supervised_prediction"].notna().all()
    assert out["is_novel_flagged"].dtype == bool
    assert (out["prediction"] == "Suspected_ZeroDay").equals(out["is_novel_flagged"])
    assert "suspected_zero_day_pct" in out.columns
    assert (out["suspected_zero_day_pct"] >= 0).all() and (out["suspected_zero_day_pct"] <= 100).all()

    out_tier = detect_novel_dataframe(
        df,
        supervised_dir=sup_dir,
        anomaly_dir=anom_dir,
        novel_label="Suspected_ZeroDay",
        confidence_threshold=0.99,
        require_low_confidence=True,
        tier_strong_label="Suspected_ZeroDay_Strong",
        tier_percentile=90.0,
    )
    novel = out_tier[out_tier["is_novel_flagged"]]
    if len(novel) > 0:
        assert novel["prediction"].isin(["Suspected_ZeroDay", "Suspected_ZeroDay_Strong"]).all()
