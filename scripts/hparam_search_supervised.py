#!/usr/bin/env python3
"""Randomized search for HistGradientBoosting on numeric features (inner CV on train)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline

from hawk_eye.features import FeatureSpec, infer_feature_columns, split_xy
from hawk_eye.io import read_table
from hawk_eye.preprocessing_supervised import build_numeric_preprocessor


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="Training CSV/Parquet.")
    ap.add_argument("--label-col", default="Label")
    ap.add_argument("--out", default="reports/hparam_best.json")
    ap.add_argument("--n-iter", type=int, default=12)
    ap.add_argument("--cv", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = read_table(args.data)
    spec = FeatureSpec(feature_columns=[], label_column=args.label_col, id_columns=[])
    X_df, y = split_xy(df, spec)
    cols = infer_feature_columns(df, drop=[args.label_col])
    X_df = X_df[cols].select_dtypes(include=[np.number])
    numeric_columns = list(X_df.columns)
    pre = build_numeric_preprocessor(numeric_columns)
    pipe = Pipeline(
        steps=[
            ("preprocessor", pre),
            (
                "model",
                HistGradientBoostingClassifier(
                    random_state=args.seed,
                    early_stopping=True,
                    validation_fraction=0.1,
                ),
            ),
        ]
    )
    param_dist = {
        "model__learning_rate": [0.03, 0.06, 0.1],
        "model__max_depth": [6, 8, 10, 12],
        "model__max_leaf_nodes": [31, 63, 127],
        "model__min_samples_leaf": [10, 20, 40],
        "model__l2_regularization": [0.0, 0.05, 0.1],
        "model__max_iter": [200, 400],
    }
    cv = StratifiedKFold(n_splits=args.cv, shuffle=True, random_state=args.seed)
    search = RandomizedSearchCV(
        pipe,
        param_dist,
        n_iter=args.n_iter,
        cv=cv,
        scoring="f1_macro",
        random_state=args.seed,
        n_jobs=-1,
        verbose=1,
    )
    search.fit(X_df, y)
    best = {"best_params": search.best_params_, "best_score_macro_f1": float(search.best_score_)}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(best, indent=2))
    print(json.dumps(best, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
