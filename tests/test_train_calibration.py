from __future__ import annotations

from pathlib import Path

import pandas as pd

from hawk_eye.bundle import load as load_bundle
from hawk_eye.bundle import save as save_bundle
from hawk_eye.train import _build_pipeline


def test_calibrated_classifier_bundle_predicts_proba(tmp_path: Path) -> None:
    X = pd.read_csv(Path("tests/fixtures/sample_features.csv"))
    y = pd.read_csv(Path("tests/fixtures/sample_labels.csv"))["label"].to_numpy()

    pipe = _build_pipeline(list(X.columns), logistic_class_weight=None)
    pipe.fit(X, y)
    pre = pipe.named_steps["preprocessor"]
    clf = pipe.named_steps["model"]

    from sklearn.calibration import CalibratedClassifierCV

    # small calibration set = same data for smoke (real use: separate val)
    Xt = pre.transform(X)
    cal = CalibratedClassifierCV(estimator=clf, cv="prefit", method="sigmoid")
    cal.fit(Xt, y)

    bundle_dir = tmp_path / "cal"
    save_bundle(
        bundle_dir=bundle_dir,
        model=cal,
        preprocessor=pre,
        feature_columns=list(X.columns),
        config={"bundle_version": "t", "calibrated": True},
        metadata={},
    )

    b = load_bundle(bundle_dir)
    Xt2 = b.preprocessor.transform(X)
    proba = b.model.predict_proba(Xt2)
    assert proba.shape[0] == len(X)
    assert (proba >= 0).all() and (proba <= 1).all().all()
