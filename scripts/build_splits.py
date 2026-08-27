#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from hawk_eye.preprocess import PreprocessConfig, build_manifest, preprocess_to_interim, write_manifest
from hawk_eye.split import SplitConfig, split_train_val_test, write_splits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", required=True, help="Directory containing raw CSVs (data/raw/<slug>/).")
    ap.add_argument("--dataset-slug", required=True, help="Pinned Kaggle slug (owner/slug).")
    ap.add_argument(
        "--label-col",
        default="Label",
        help="Label column in raw CSVs (default: Label).",
    )
    ap.add_argument(
        "--out-dir",
        default="data/processed",
        help="Output directory for splits (default: data/processed).",
    )
    ap.add_argument(
        "--interim",
        default="data/interim/merged.csv",
        help="Optional merged file path (csv/parquet).",
    )
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test-size", type=float, default=0.2)
    ap.add_argument("--val-size", type=float, default=0.2)
    ap.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional cap: read only a head slice per file so total rows stays near this (saves RAM).",
    )
    args = ap.parse_args()

    cfg = PreprocessConfig(label_column=args.label_col)
    df = preprocess_to_interim(
        raw_dir=args.raw_dir,
        out_path=args.interim,
        cfg=cfg,
        max_rows_total=args.max_rows,
    )

    split_cfg = SplitConfig(
        seed=args.seed,
        test_size=args.test_size,
        val_size=args.val_size,
        stratify=True,
    )
    train_df, val_df, test_df = split_train_val_test(df, label_column=args.label_col, cfg=split_cfg)
    write_splits(train_df=train_df, val_df=val_df, test_df=test_df, out_dir=args.out_dir, fmt="csv")

    manifest = build_manifest(
        raw_dir=args.raw_dir,
        dataset_slug=args.dataset_slug,
        rows=int(df.shape[0]),
        columns=list(df.columns),
        split_seed=args.seed,
        label_column=args.label_col,
    )
    write_manifest(manifest, Path(args.out_dir) / "preprocessing_manifest.json")

    print(f"Wrote splits to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

