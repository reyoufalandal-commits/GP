#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate UNSW-aware novelty calibrator outcomes.")
    ap.add_argument("--input", default="reports/unsw_scored_with_calibrator.parquet")
    ap.add_argument("--label-col", default="Label")
    ap.add_argument(
        "--known-label",
        action="append",
        default=[],
        help="Known labels (repeatable). Non-known are treated unknown.",
    )
    ap.add_argument("--out", default="reports/unsw_novelty_calibrator_eval.json")
    args = ap.parse_args()

    df = pd.read_parquet(args.input) if str(args.input).endswith(".parquet") else pd.read_csv(args.input)
    known = set(args.known_label)
    is_unknown = ~df[args.label_col].astype(str).isin(known)
    pred = df["novelty_calibrated_flag"].astype(bool)
    rec = float((pred & is_unknown).sum() / max(int(is_unknown.sum()), 1))
    alert_rate = float(pred.mean())
    known_fpr = float((pred & ~is_unknown).sum() / max(int((~is_unknown).sum()), 1))

    payload = {
        "rows": int(len(df)),
        "unknown_rows": int(is_unknown.sum()),
        "calibrator_alert_rate": alert_rate,
        "calibrator_unknown_recall": rec,
        "calibrator_known_alert_rate": known_fpr,
    }
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
