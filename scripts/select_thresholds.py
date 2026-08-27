#!/usr/bin/env python3
"""
Pick ``block_min_proba`` for soc_policy from a labeled validation set + scored predictions.

Requires columns: label column, ``prediction``, ``proba_max`` (from hawk_eye.score).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from hawk_eye.io import read_table


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Scored val CSV/Parquet with labels.")
    ap.add_argument("--label-col", default="Label", help="Ground-truth label column.")
    ap.add_argument("--benign-label", default="BENIGN", help="Benign class string.")
    ap.add_argument(
        "--max-fpr",
        type=float,
        default=0.01,
        help="Max fraction of benign rows that may get block_candidate at chosen threshold.",
    )
    ap.add_argument("--out", default="reports/thresholds.json", help="Output JSON path.")
    args = ap.parse_args()

    df = read_table(args.input)
    for c in ("prediction", "proba_max", args.label_col):
        if c not in df.columns:
            raise SystemExit(f"Missing column: {c}")

    benign = df[df[args.label_col].astype(str).str.strip() == args.benign_label]
    if len(benign) == 0:
        raise SystemExit("No benign rows; cannot estimate FPR.")

    # Candidate blocks: predicted not-benign with proba_max >= T
    pred = benign["prediction"].astype(str).str.strip()
    pm = benign["proba_max"].to_numpy(dtype=np.float64)
    is_attack_pred = pred != args.benign_label

    best_t = 0.99
    for t in np.linspace(0.5, 0.999, 200):
        mask = is_attack_pred & (pm >= t)
        fpr = float(mask.mean())
        if fpr <= args.max_fpr:
            best_t = float(t)

    payload = {
        "block_min_proba": best_t,
        "target_max_benign_fpr": args.max_fpr,
        "benign_rows": int(len(benign)),
        "note": "Heuristic: FPR = fraction of benign rows with attack prediction and proba_max >= threshold.",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
