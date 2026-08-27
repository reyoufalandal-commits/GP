#!/usr/bin/env python3
"""Merge supervised score output with anomaly scores on row index. Same row count and order required."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--supervised", required=True, help="CSV from hawk_eye.score")
    ap.add_argument("--anomaly", required=True, help="CSV from hawk_eye.score_anomaly")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    s = pd.read_csv(args.supervised)
    a = pd.read_csv(args.anomaly)
    if len(s) != len(a):
        raise ValueError(f"Row count mismatch: supervised={len(s)} anomaly={len(a)}")
    out = pd.concat([s, a.add_prefix("anomaly_")], axis=1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f"Wrote {args.out} rows={len(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
