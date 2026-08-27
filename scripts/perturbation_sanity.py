#!/usr/bin/env python3
"""Add small Gaussian noise to numeric features; report prediction flip rate (evasion sanity)."""
from __future__ import annotations

import argparse
import json

import numpy as np

from hawk_eye.bundle import load as load_bundle
from hawk_eye.features import align_columns_strict
from hawk_eye.io import read_table


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--noise-std-frac", type=float, default=0.02, help="Noise std as fraction of column std.")
    ap.add_argument("--max-rows", type=int, default=5000)
    args = ap.parse_args()

    df = read_table(args.input)
    bundle = load_bundle(args.model_dir)
    X = align_columns_strict(df, bundle.feature_columns)
    if len(X) > args.max_rows:
        X = X.iloc[: args.max_rows]
    Xt = bundle.preprocessor.transform(X)
    model = bundle.model
    base = model.predict(Xt)
    rng = np.random.default_rng(42)
    Xn = np.asarray(Xt, dtype=np.float64)
    for j in range(Xn.shape[1]):
        s = float(np.std(Xn[:, j])) or 1.0
        Xn[:, j] += rng.normal(0, args.noise_std_frac * s, size=len(Xn))
    pert = model.predict(Xn)
    flips = float(np.mean(base != pert))
    out = {"prediction_flip_rate": flips, "noise_std_frac": args.noise_std_frac, "rows": len(X)}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
