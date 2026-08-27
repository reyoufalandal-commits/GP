#!/usr/bin/env python3
"""
Build tiny on-disk model bundles under artifacts/ for CI and local smoke tests.

Aligns binary, supervised, and anomaly bundles on the same feature_columns (required by
attack_uncertain_dataframe). Uses synthetic data; not for accuracy benchmarks.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Repo root (parent of scripts/)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from hawk_eye import __version__  # noqa: E402
from hawk_eye.anomaly_bundle import save_anomaly_bundle  # noqa: E402
from hawk_eye.bundle import save as save_bundle  # noqa: E402
from hawk_eye.train import _build_pipeline  # noqa: E402
from hawk_eye.train_anomaly import train_iforest  # noqa: E402


FEATURE_COLUMNS = [
    "Protocol",
    "Flow Duration",
    "Total Fwd Packets",
    "Total Backward Packets",
    "Flow Bytes/s",
    "Flow Packets/s",
]


def main() -> int:
    rng = np.random.default_rng(42)
    n = 400
    X = rng.normal(size=(n, len(FEATURE_COLUMNS)))
    df = pd.DataFrame(X, columns=FEATURE_COLUMNS)

    df_bin = df.copy()
    df_bin["label"] = np.where(rng.random(n) > 0.45, "Benign", "Attack")

    df_sup = df.copy()
    df_sup["label"] = rng.choice(np.array(["Benign", "DoS", "PortScan"], dtype=object), size=n)

    pipe_bin = _build_pipeline(FEATURE_COLUMNS, logistic_class_weight="balanced", model_type="logistic")
    pipe_bin.fit(df_bin.drop(columns=["label"]), df_bin["label"])

    pipe_sup = _build_pipeline(FEATURE_COLUMNS, logistic_class_weight="balanced", model_type="logistic")
    pipe_sup.fit(df_sup.drop(columns=["label"]), df_sup["label"])

    art = ROOT / "artifacts"
    bin_dir = art / "hawk-eye-binary"
    sup_dir = art / "current"
    ano_dir = art / "current_anomaly"

    save_bundle(
        bundle_dir=bin_dir,
        model=pipe_bin.named_steps["model"],
        preprocessor=pipe_bin.named_steps["preprocessor"],
        feature_columns=FEATURE_COLUMNS,
        config={
            "bundle_version": __version__,
            "sklearn_model_type": "logistic",
            "binary_benign_vs_attack": True,
            "classes": list(pipe_bin.named_steps["model"].classes_),
        },
        metadata={"ci_minimal": True, "role": "binary"},
    )
    save_bundle(
        bundle_dir=sup_dir,
        model=pipe_sup.named_steps["model"],
        preprocessor=pipe_sup.named_steps["preprocessor"],
        feature_columns=FEATURE_COLUMNS,
        config={
            "bundle_version": __version__,
            "sklearn_model_type": "logistic",
            "classes": list(pipe_sup.named_steps["model"].classes_),
        },
        metadata={"ci_minimal": True, "role": "supervised_multiclass"},
    )

    benign = df_sup[df_sup["label"] == "Benign"].copy()
    if len(benign) < 20:
        benign = df_sup.head(100)
    val = benign.iloc[: max(10, len(benign) // 5)]
    tr = benign.iloc[len(val) :]
    if len(tr) < 10:
        tr = df_sup.head(150)
        val = df_sup.iloc[150:200]

    pre, iforest = train_iforest(
        X_train=tr[FEATURE_COLUMNS],
        feature_columns=FEATURE_COLUMNS,
        contamination=0.05,
    )
    Xt_val = pre.transform(val[FEATURE_COLUMNS])
    if hasattr(Xt_val, "toarray"):
        Xt_val = Xt_val.toarray()
    scores = -iforest.score_samples(Xt_val)
    thr = float(np.percentile(scores, 99.0))
    cfg = {
        "model_type": "isolation_forest",
        "bundle_version": __version__,
        "threshold": thr,
        "score_direction": "higher_is_anomaly",
        "percentile": 99.0,
        "contamination": 0.05,
        "label_column": "label",
    }
    save_anomaly_bundle(
        bundle_dir=ano_dir,
        preprocessor=pre,
        feature_columns=FEATURE_COLUMNS,
        config=cfg,
        metadata={"ci_minimal": True, "role": "anomaly"},
        sklearn_model=iforest,
    )

    rep = ROOT / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "thresholds_fusion_selected.json").write_text(
        json.dumps(
            {
                "min_p_attack_known": 0.7,
                "min_szd_uncertain": 70.0,
                "min_open_set_uncertain": 0.6,
            },
            indent=2,
        )
    )
    (rep / "unsw_external_profiles.json").write_text(
        json.dumps({"balanced_profile": {"thresholds": {}}, "high_recall_profile": {}}, indent=2)
    )

    print(json.dumps({"ok": True, "artifacts": [str(bin_dir), str(sup_dir), str(ano_dir)]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
