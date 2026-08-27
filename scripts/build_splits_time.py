#!/usr/bin/env python3
"""Time-ordered train/val/test split (reduces temporal leakage vs random stratified split)."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from hawk_eye.io import write_table


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Merged CSV/Parquet with a time column.")
    ap.add_argument("--time-col", required=True, help="Monotonic time column (numeric or datetime).")
    ap.add_argument("--out-dir", default="data/processed")
    ap.add_argument("--train-frac", type=float, default=0.64)
    ap.add_argument("--val-frac", type=float, default=0.16)
    args = ap.parse_args()

    df = pd.read_csv(args.input) if args.input.endswith(".csv") else pd.read_parquet(args.input)
    if args.time_col not in df.columns:
        raise SystemExit(f"Missing time column {args.time_col!r}")

    df = df.sort_values(args.time_col).reset_index(drop=True)
    n = len(df)
    a = int(n * args.train_frac)
    b = int(n * (args.train_frac + args.val_frac))
    train_df, val_df, test_df = df.iloc[:a], df.iloc[a:b], df.iloc[b:]
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fmt = "csv"
    write_table(train_df, out / f"train.{fmt}")
    write_table(val_df, out / f"val.{fmt}")
    write_table(test_df, out / f"test.{fmt}")
    print(f"Wrote time-ordered splits to {out} (train={len(train_df)} val={len(val_df)} test={len(test_df)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
