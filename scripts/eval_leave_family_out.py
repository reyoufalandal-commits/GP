#!/usr/bin/env python3
"""
Proxy "unknown family" eval: train without label A, test only on label A (multiclass).

Requires enough rows per class; drops rare classes if needed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.pipeline import Pipeline

from hawk_eye.features import FeatureSpec, infer_feature_columns, split_xy
from hawk_eye.io import read_table
from hawk_eye.preprocessing_supervised import build_numeric_preprocessor


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--label-col", default="Label")
    ap.add_argument("--holdout-label", required=True, help="Attack family to hold out of training.")
    ap.add_argument("--out", default="reports/leave_family_out.json")
    args = ap.parse_args()

    df = read_table(args.data)
    spec = FeatureSpec(feature_columns=[], label_column=args.label_col, id_columns=[])
    X_df, y = split_xy(df, spec)
    cols = infer_feature_columns(df, drop=[args.label_col])
    X_df = X_df[cols].select_dtypes(include=[np.number])
    y = np.asarray(y)

    test_mask = y == args.holdout_label
    train_mask = ~test_mask
    if test_mask.sum() < 5 or train_mask.sum() < 20:
        raise SystemExit("Not enough rows for holdout split.")

    pipe = Pipeline(
        steps=[
            ("preprocessor", build_numeric_preprocessor(list(X_df.columns))),
            ("model", LogisticRegression(max_iter=1000)),
        ]
    )
    pipe.fit(X_df.iloc[np.where(train_mask)[0]], y[train_mask])
    pred = pipe.predict(X_df.iloc[np.where(test_mask)[0]])
    rep = classification_report(y[test_mask], pred, output_dict=True, zero_division=0)
    payload = {
        "holdout_label": args.holdout_label,
        "test_rows": int(test_mask.sum()),
        "classification_report_holdout_only": rep,
        "note": "Proxy for unseen family — not a real zero-day benchmark.",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
