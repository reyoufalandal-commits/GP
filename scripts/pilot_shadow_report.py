#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import classification_report

from hawk_eye.io import read_table


def main() -> int:
    ap = argparse.ArgumentParser(description="Pilot shadow/canary comparison report.")
    ap.add_argument("--predictions", required=True, help="Triaged output with decision_label and case_id.")
    ap.add_argument("--analyst-labels", required=True, help="CSV/Parquet with case_id + analyst_label.")
    ap.add_argument("--case-id-col", default="case_id")
    ap.add_argument("--prediction-col", default="decision_label")
    ap.add_argument("--analyst-col", default="analyst_label")
    ap.add_argument("--out", default="reports/pilot_shadow_report.json")
    args = ap.parse_args()

    pred = read_table(args.predictions)
    ann = read_table(args.analyst_labels)
    for c in (args.case_id_col, args.prediction_col):
        if c not in pred.columns:
            raise SystemExit(f"Missing prediction column: {c}")
    for c in (args.case_id_col, args.analyst_col):
        if c not in ann.columns:
            raise SystemExit(f"Missing analyst column: {c}")

    merged = pred[[args.case_id_col, args.prediction_col]].merge(
        ann[[args.case_id_col, args.analyst_col]],
        on=args.case_id_col,
        how="inner",
    )
    if merged.empty:
        raise SystemExit("No matching cases between predictions and analyst labels.")
    rep = classification_report(
        merged[args.analyst_col].astype(str),
        merged[args.prediction_col].astype(str),
        output_dict=True,
        zero_division=0,
    )
    payload = {
        "rows_compared": int(len(merged)),
        "prediction_col": args.prediction_col,
        "analyst_col": args.analyst_col,
        "classification_report": rep,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
