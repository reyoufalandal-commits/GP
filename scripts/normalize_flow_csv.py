#!/usr/bin/env python3
"""Normalize CICFlowMeter / CICIDS CSV headers to match a supervised bundle feature contract."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from hawk_eye.bundle import load as load_bundle
from hawk_eye.cic_normalize import (
    dataframe_matches_features,
    load_extra_aliases,
    normalize_flow_dataframe,
)
from hawk_eye.io import read_table, write_table
from hawk_eye.paths import resolve_model_dir


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="CSV/Parquet from CICFlowMeter or similar.")
    ap.add_argument("--output", required=True, help="Normalized CSV/Parquet for hawk_eye.score.")
    ap.add_argument("--model-dir", default=None, help="Bundle with feature_columns.json.")
    ap.add_argument(
        "--label-col",
        default="",
        help="Optional label column to keep (e.g. Label for evaluation).",
    )
    ap.add_argument(
        "--aliases",
        default="",
        help="Optional JSON file: {\"Alternate Name\": \"Canonical Name\"}.",
    )
    args = ap.parse_args()

    bdir = resolve_model_dir(model_dir=args.model_dir)
    bundle = load_bundle(bdir)
    feat = bundle.feature_columns

    if args.aliases:
        extra = load_extra_aliases(Path(args.aliases))
    else:
        default_aliases = Path("config/cic_column_aliases.json")
        extra = load_extra_aliases(default_aliases if default_aliases.exists() else None)

    df = read_table(args.input)
    label_col = args.label_col.strip() or None

    norm = normalize_flow_dataframe(df, feature_columns=feat, label_column=label_col, extra_aliases=extra)

    missing, extra_cols = dataframe_matches_features(norm, feat, label_column=label_col)
    if missing:
        print(
            json.dumps(
                {
                    "status": "incomplete",
                    "missing_features": missing,
                    "extra_columns": extra_cols[:50],
                    "hint": "Fix tool export or extend config/cic_column_aliases.json",
                },
                indent=2,
            )
        )
        return 2

    out_cols = list(feat)
    if label_col and label_col in norm.columns:
        out_cols = out_cols + [label_col]
    out = norm[[c for c in out_cols if c in norm.columns]]

    write_table(out, args.output)
    print(json.dumps({"status": "ok", "rows": len(out), "columns": len(out.columns), "output": str(Path(args.output).resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
