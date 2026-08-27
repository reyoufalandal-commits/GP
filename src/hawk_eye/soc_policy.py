"""
SOC-style *recommendations* from scored flows — not automatic blocking.

Use calibrated thresholds, human review, and playbooks. This module adds explicit
``soc_action`` / ``soc_reason`` columns for SIEM export or queues.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from hawk_eye.io import read_table, write_table


def _norm_label(x: Any) -> str:
    return str(x).strip()


def apply_soc_policy(
    df: pd.DataFrame,
    *,
    benign_labels: frozenset[str],
    pred_col: str = "prediction",
    proba_col: str = "proba_max",
    block_min_proba: float = 0.92,
    anomaly_col: str | None = None,
    anomaly_benign_escalate: float | None = None,
) -> pd.DataFrame:
    """
    Attach ``soc_action`` and ``soc_reason``.

    - ``allow`` — predicted benign and (if anomaly given) below escalation cutoff.
    - ``block_candidate`` — predicted attack and ``proba_max`` >= ``block_min_proba`` (if proba present).
    - ``alert_review`` — attack prediction with low confidence, missing proba, or benign + high anomaly.

    ``anomaly_benign_escalate``: if set, benign predictions with ``anomaly_col`` >= this value
    become ``alert_review`` (never auto-block on anomaly alone here).
    """
    if pred_col not in df.columns:
        raise ValueError(f"Missing column {pred_col!r}")

    preds = df[pred_col].map(_norm_label)
    benign_set = {_norm_label(x) for x in benign_labels}

    has_proba = proba_col in df.columns
    proba = df[proba_col].to_numpy(dtype=np.float64) if has_proba else None

    anom = None
    if anomaly_col is not None:
        if anomaly_col not in df.columns:
            raise ValueError(f"Missing column {anomaly_col!r}")
        anom = df[anomaly_col].to_numpy(dtype=np.float64)

    n = len(df)
    actions: list[str] = []
    reasons: list[str] = []

    for i in range(n):
        p = preds.iloc[i]
        is_benign = p in benign_set

        if is_benign:
            if anom is not None and anomaly_benign_escalate is not None:
                if float(anom[i]) >= float(anomaly_benign_escalate):
                    actions.append("alert_review")
                    reasons.append("benign_prediction_high_anomaly_score")
                    continue
            actions.append("allow")
            reasons.append("benign_prediction")
            continue

        if not has_proba or proba is None or not np.isfinite(proba[i]):
            actions.append("alert_review")
            reasons.append("attack_prediction_missing_or_invalid_proba")
            continue

        pm = float(proba[i])
        if pm >= float(block_min_proba):
            actions.append("block_candidate")
            reasons.append(f"attack_high_confidence_proba_max={pm:.4f}")
        else:
            actions.append("alert_review")
            reasons.append(f"attack_low_confidence_proba_max={pm:.4f}")

    return df.assign(soc_action=actions, soc_reason=reasons)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Add soc_action / soc_reason from scored predictions (policy helper, not enforcement)."
    )
    ap.add_argument("--input", required=True, help="Scored CSV/Parquet (e.g. from hawk_eye.score).")
    ap.add_argument("--output", required=True, help="Output path with extra columns.")
    ap.add_argument(
        "--benign-label",
        action="append",
        default=None,
        help="Label value treated as benign (repeatable). Default: BENIGN,benign",
    )
    ap.add_argument("--pred-col", default="prediction", help="Predicted class column.")
    ap.add_argument("--proba-col", default="proba_max", help="Max class probability column.")
    ap.add_argument(
        "--block-min-proba",
        type=float,
        default=0.92,
        help="Minimum proba_max to emit block_candidate for attack predictions.",
    )
    ap.add_argument(
        "--anomaly-col",
        default=None,
        help="Optional anomaly score column (e.g. from score_anomaly).",
    )
    ap.add_argument(
        "--anomaly-benign-escalate",
        type=float,
        default=None,
        help="If set, benign rows with anomaly score >= this become alert_review.",
    )
    ap.add_argument(
        "--thresholds-file",
        default=None,
        help="JSON from scripts/select_thresholds.py (uses block_min_proba if present).",
    )
    args = ap.parse_args()

    labels: list[str] = args.benign_label if args.benign_label else []
    if not labels:
        labels = ["BENIGN", "benign"]
    benign = frozenset(_norm_label(x) for x in labels)

    block_min = float(args.block_min_proba)
    if args.thresholds_file:
        data = json.loads(Path(args.thresholds_file).read_text())
        if "block_min_proba" in data:
            block_min = float(data["block_min_proba"])

    df = read_table(args.input)
    out = apply_soc_policy(
        df,
        benign_labels=benign,
        pred_col=args.pred_col,
        proba_col=args.proba_col,
        block_min_proba=block_min,
        anomaly_col=args.anomaly_col,
        anomaly_benign_escalate=args.anomaly_benign_escalate,
    )
    write_table(out, args.output)

    summary = {
        "rows": len(out),
        "output": str(Path(args.output).resolve()),
        "soc_action_counts": out["soc_action"].value_counts().to_dict(),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
