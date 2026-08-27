from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from hawk_eye.anomaly_bundle import load_anomaly_bundle
from hawk_eye.anomaly_score import score_frame_anomaly
from hawk_eye.train_anomaly import train_iforest


def test_iforest_anomaly_train_and_score(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    n = 400
    Xb = rng.normal(0, 1, size=(n, 4))
    df_tr = pd.DataFrame(Xb, columns=[f"f{i}" for i in range(4)])
    df_tr["Label"] = "BENIGN"

    pre, clf = train_iforest(X_train=df_tr.drop(columns=["Label"]), feature_columns=list(df_tr.columns[:-1]), contamination=0.05)
    Xt_val = pre.transform(df_tr.drop(columns=["Label"]))
    scores = -clf.score_samples(Xt_val)
    thr = float(np.percentile(scores, 99.0))

    from hawk_eye.anomaly_bundle import save_anomaly_bundle

    bundle_dir = tmp_path / "anom"
    save_anomaly_bundle(
        bundle_dir=bundle_dir,
        preprocessor=pre,
        feature_columns=[f"f{i}" for i in range(4)],
        config={
            "model_type": "isolation_forest",
            "threshold": thr,
            "bundle_version": "test",
        },
        sklearn_model=clf,
    )

    b = load_anomaly_bundle(bundle_dir)
    s = score_frame_anomaly(df_tr.drop(columns=["Label"]), b)
    assert len(s) == n
    assert (s <= thr * 1.01).mean() >= 0.95
