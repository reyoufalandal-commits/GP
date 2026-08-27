#!/usr/bin/env python3
"""Check that a table has the same feature columns as a supervised bundle (for live scoring)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from hawk_eye.bundle import load as load_bundle
from hawk_eye.io import read_table
from hawk_eye.paths import resolve_model_dir


def _read_limited(path: str | Path, max_rows: int) -> pd.DataFrame:
    """Avoid loading huge files when only schema/dtypes are needed."""
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p, nrows=max_rows)
    df = read_table(p)
    return df.head(max_rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="CSV/Parquet to validate (may include Label).")
    ap.add_argument(
        "--model-dir",
        default=None,
        help="Supervised bundle (default: HAWK_EYE_MODEL_DIR / artifacts/current).",
    )
    ap.add_argument(
        "--max-rows",
        type=int,
        default=5000,
        help="Rows to scan for dtype check (default 5000).",
    )
    args = ap.parse_args()

    bdir = resolve_model_dir(model_dir=args.model_dir)
    bundle = load_bundle(bdir)
    df = _read_limited(args.input, max(1, args.max_rows))
    expected = bundle.feature_columns

    missing = [c for c in expected if c not in df.columns]
    if missing:
        print(f"FAIL: missing {len(missing)} columns: {missing[:20]}{'...' if len(missing) > 20 else ''}", file=sys.stderr)
        return 1

    sub = df[expected].head(max(1, args.max_rows))
    bad: list[str] = []
    for c in expected:
        if not pd.api.types.is_numeric_dtype(sub[c]):
            bad.append(c)
        else:
            s = sub[c].to_numpy(dtype=float, copy=False)
            if not np.isfinite(s).all():
                bad.append(f"{c}(nan_or_inf)")

    if bad:
        print(f"FAIL: non-numeric or non-finite values in: {bad[:30]}", file=sys.stderr)
        return 1

    h = bundle.config.get("feature_columns_hash", "")
    extra = f" feature_columns_hash={h}" if h else ""
    print(f"OK: {len(expected)} feature columns match bundle {bundle.dir.name}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
