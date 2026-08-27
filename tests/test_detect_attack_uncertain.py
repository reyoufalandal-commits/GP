from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from hawk_eye.anomaly_bundle import save_anomaly_bundle
from hawk_eye.bundle import save as save_bundle
from hawk_eye.detect_novel import attack_uncertain_dataframe
from hawk_eye.labels_binary import BINARY_ATTACK, default_benign_labels, to_benign_attack
from hawk_eye.train import _build_pipeline
from hawk_eye.train_anomaly import train_iforest


def test_attack_uncertain_requires_binary_bundle(tmp_path: Path) -> None:
    X = pd.read_csv(Path("tests/fixtures/sample_features.csv"))
    y_raw = pd.read_csv(Path("tests/fixtures/sample_labels.csv"))["label"].to_numpy()
    df = X.copy()

    y_multi = y_raw
    pipe = _build_pipeline(list(X.columns), logistic_class_weight=None)
    pipe.fit(X, y_multi)

    sup_dir = tmp_path / "sup"
    save_bundle(
        bundle_dir=sup_dir,
        model=pipe.named_steps["model"],
        preprocessor=pipe.named_steps["preprocessor"],
        feature_columns=list(X.columns),
        config={"bundle_version": "t", "binary_benign_vs_attack": False},
        metadata={},
    )

    benign_only = df[y_multi == "benign"].copy()
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

    y_bin = to_benign_attack(y_raw, default_benign_labels())
    pipe_b = _build_pipeline(list(X.columns), logistic_class_weight=None)
    pipe_b.fit(X, y_bin)
    bin_dir = tmp_path / "bin"
    save_bundle(
        bundle_dir=bin_dir,
        model=pipe_b.named_steps["model"],
        preprocessor=pipe_b.named_steps["preprocessor"],
        feature_columns=list(X.columns),
        config={"bundle_version": "t", "binary_benign_vs_attack": True},
        metadata={},
    )

    out = attack_uncertain_dataframe(
        df,
        binary_dir=bin_dir,
        supervised_dir=sup_dir,
        anomaly_dir=anom_dir,
        novel_label="Suspected_ZeroDay",
        confidence_threshold=0.99,
        require_low_confidence=True,
        min_szd_pct_for_attack_uncertain=100.0,
    )
    assert len(out) == len(df)
    assert "binary_prediction" in out.columns
    assert "p_attack" in out.columns
    assert "is_attack_uncertain" in out.columns
    assert (out["is_attack_uncertain"] <= out["binary_prediction"].eq(BINARY_ATTACK)).all()
