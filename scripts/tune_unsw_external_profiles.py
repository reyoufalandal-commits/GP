#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from hawk_eye.novelty_calibrator import apply_calibrator, fit_calibrator


KNOWN_LABELS = {
    "Benign",
    "DDoS",
    "FTP-Patator",
    "DoS slowloris",
    "PortScan",
    "Bot",
    "Web Attack � Brute Force",
}


def _metrics(pred: pd.Series, is_unknown: pd.Series, is_known: pd.Series) -> dict[str, float]:
    pred_bool = pred.astype(bool)
    return {
        "unknown_recall": float((pred_bool & is_unknown).sum() / max(int(is_unknown.sum()), 1)),
        "alert_rate": float(pred_bool.mean()),
        "known_alert_rate": float((pred_bool & is_known).sum() / max(int(is_known.sum()), 1)),
    }


def _pick_best(rows: list[dict[str, Any]], *, max_known_alert: float, max_alert: float) -> dict[str, Any]:
    candidates = [
        r
        for r in rows
        if float(r["known_alert_rate"]) <= max_known_alert and float(r["alert_rate"]) <= max_alert
    ]
    if not candidates:
        return max(rows, key=lambda x: float(x["unknown_recall"]))
    return max(candidates, key=lambda x: float(x["unknown_recall"]))


def main() -> int:
    ap = argparse.ArgumentParser(description="Tune external unknown profiles on UNSW scored set.")
    ap.add_argument("--input", default="reports/unsw_scored_labeled.parquet")
    ap.add_argument("--out", default="reports/unsw_external_profiles.json")
    args = ap.parse_args()

    df = pd.read_parquet(args.input) if str(args.input).endswith(".parquet") else pd.read_csv(args.input)
    labels = df["Label"].astype(str)
    is_unknown = ~labels.isin(KNOWN_LABELS)
    is_known = ~is_unknown

    rows: list[dict[str, Any]] = []
    for q in [0.90, 0.93, 0.95, 0.97, 0.98, 0.99]:
        o = float(df.loc[is_known, "open_set_ood_score"].quantile(q))
        s = float(df.loc[is_known, "suspected_zero_day_pct"].quantile(q))
        a = float(df.loc[is_known, "anomaly_score"].quantile(q))
        pred = (df["suspected_zero_day_pct"] >= s) | (df["anomaly_score"] >= a) | (df["open_set_ood_score"] >= o)
        m = _metrics(pred, is_unknown, is_known)
        rows.append(
            {
                "method": "adaptive",
                "quantile": q,
                **m,
                "thresholds": {
                    "open_set_ood_score": o,
                    "suspected_zero_day_pct": s,
                    "anomaly_score": a,
                },
            }
        )

    feature_cols = [
        "p_attack",
        "suspected_zero_day_pct",
        "anomaly_score",
        "open_set_ood_score",
        "max_class_probability",
    ]
    for budget in [0.08, 0.10, 0.12, 0.15, 0.20, 0.25]:
        bundle, _ = fit_calibrator(
            df,
            label_col="Label",
            known_labels=KNOWN_LABELS,
            feature_columns=feature_cols,
            max_alert_rate=budget,
            random_state=42,
        )
        pred = apply_calibrator(df, bundle)["novelty_calibrated_flag"]
        m = _metrics(pred, is_unknown, is_known)
        rows.append(
            {
                "method": "calibrator",
                "max_alert_budget": budget,
                "chosen_threshold": float(bundle.threshold),
                **m,
            }
        )

    balanced = _pick_best(rows, max_known_alert=0.08, max_alert=0.20)
    high_recall = _pick_best(rows, max_known_alert=0.12, max_alert=0.26)

    payload = {
        "rows": int(len(df)),
        "unknown_rows": int(is_unknown.sum()),
        "balanced_profile": balanced,
        "high_recall_profile": high_recall,
        "all_candidates": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"balanced_profile": balanced, "high_recall_profile": high_recall}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
