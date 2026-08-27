#!/usr/bin/env python3
"""
Lightweight drift check: compare mean/std of numeric columns between a reference table
(e.g. data/processed/train.csv) and a new sample (e.g. live flows).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hawk_eye.drift_compare import compare_numeric_drift


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True, help="Reference CSV/Parquet (e.g. train split).")
    ap.add_argument("--sample", required=True, help="New data to compare.")
    ap.add_argument(
        "--columns",
        default="",
        help="Comma-separated columns to compare; empty = intersection of numeric columns.",
    )
    ap.add_argument("--max-rows-ref", type=int, default=50_000)
    ap.add_argument("--max-rows-sample", type=int, default=50_000)
    ap.add_argument("--out-json", default=None, help="Optional path to write comparison JSON.")
    args = ap.parse_args()

    cols = [c.strip() for c in args.columns.split(",") if c.strip()] if args.columns.strip() else None
    rows = compare_numeric_drift(
        args.reference,
        args.sample,
        columns=cols,
        max_rows_ref=args.max_rows_ref,
        max_rows_sample=args.max_rows_sample,
    )
    top = rows[:20]
    print(json.dumps(top, indent=2))
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
