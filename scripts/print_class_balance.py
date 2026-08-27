#!/usr/bin/env python3
"""Print per-class counts and imbalance ratio for a labeled training table."""
from __future__ import annotations

import argparse
import json

import pandas as pd

from hawk_eye.io import read_table


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--label-col", default="Label")
    args = ap.parse_args()
    df = read_table(args.data)
    if args.label_col not in df.columns:
        raise SystemExit(f"Missing column {args.label_col!r}")
    vc = df[args.label_col].value_counts()
    total = len(df)
    maj = int(vc.max()) if len(vc) else 0
    out = {
        "n_rows": total,
        "n_classes": len(vc),
        "majority_count": maj,
        "imbalance_ratio_max_to_min": float(maj / vc.min()) if len(vc) > 1 and vc.min() > 0 else None,
        "counts": vc.to_dict(),
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
