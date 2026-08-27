#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from hawk_eye.decision_fusion import fuse_decisions
from hawk_eye.detect_novel import attack_uncertain_dataframe
from hawk_eye.open_set import score_open_set_dataframe


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate unknown-like triage on mapped UNSW dataset.")
    ap.add_argument("--input", required=True, help="Mapped UNSW csv/parquet including Label.")
    ap.add_argument("--binary-dir", default="artifacts/hawk-eye-binary")
    ap.add_argument("--supervised-dir", default="artifacts/hawk-eye-sup")
    ap.add_argument("--anomaly-dir", default="artifacts/hawk-eye-anomaly-ae-tuned")
    ap.add_argument(
        "--known-quantile",
        type=float,
        default=0.97,
        help="Quantile on known rows to derive adaptive OOD gates (0.9..0.999).",
    )
    ap.add_argument("--out", default="reports/unsw_unknown_eval.json")
    args = ap.parse_args()

    if str(args.input).endswith(".parquet"):
        df = pd.read_parquet(args.input)
    else:
        df = pd.read_csv(args.input)
    labels = df["Label"].astype(str) if "Label" in df.columns else pd.Series(["UnknownAttack"] * len(df))
    X = df.drop(columns=["Label"]) if "Label" in df.columns else df

    scored = attack_uncertain_dataframe(
        X,
        binary_dir=args.binary_dir,
        supervised_dir=args.supervised_dir,
        anomaly_dir=args.anomaly_dir,
    )
    try:
        open_set = score_open_set_dataframe(X, bundle_dir=args.supervised_dir)
        scored = pd.concat([scored.reset_index(drop=True), open_set.reset_index(drop=True)], axis=1)
        has_open = True
    except Exception:
        has_open = False
    fused = fuse_decisions(scored, open_set_col="open_set_ood_score" if has_open else None)

    known_labels = {"Benign", "DDoS", "FTP-Patator", "DoS slowloris", "PortScan", "Bot", "Web Attack � Brute Force"}
    is_unknown = ~labels.isin(known_labels)
    unknown_recall = float((fused["decision_label"].eq("AttackUncertain") & is_unknown).sum() / max(is_unknown.sum(), 1))

    # Adaptive OOD gates on known rows to mitigate cross-dataset drift (UNSW vs CIC).
    is_known = ~is_unknown
    q = float(args.known_quantile)
    o_thr = float(scored.loc[is_known, "open_set_ood_score"].quantile(q)) if has_open else 1.0
    s_thr = float(scored.loc[is_known, "suspected_zero_day_pct"].quantile(q))
    a_thr = float(scored.loc[is_known, "anomaly_score"].quantile(q))
    adaptive_mask = (
        (scored["suspected_zero_day_pct"] >= s_thr)
        | (scored["anomaly_score"] >= a_thr)
        | ((scored["open_set_ood_score"] >= o_thr) if has_open else False)
    )
    adaptive_decision = fused["decision_label"].astype(str).copy()
    adaptive_decision.loc[adaptive_mask] = "AttackUncertain"
    adaptive_unknown_recall = float((adaptive_decision.eq("AttackUncertain") & is_unknown).sum() / max(is_unknown.sum(), 1))
    adaptive_alert_rate = float(adaptive_decision.eq("AttackUncertain").mean())
    adaptive_known_fpr = float((adaptive_decision.eq("AttackUncertain") & is_known).sum() / max(is_known.sum(), 1))

    payload = {
        "rows": int(len(fused)),
        "unknown_rows": int(is_unknown.sum()),
        "decision_counts": fused["decision_label"].value_counts().to_dict(),
        "attack_uncertain_rate": float(fused["decision_label"].eq("AttackUncertain").mean()),
        "unknown_recall_attack_uncertain": unknown_recall,
        "has_open_set": has_open,
        "adaptive_known_quantile": q,
        "adaptive_thresholds": {
            "open_set_ood_score": o_thr if has_open else None,
            "suspected_zero_day_pct": s_thr,
            "anomaly_score": a_thr,
        },
        "adaptive_unknown_recall_attack_uncertain": adaptive_unknown_recall,
        "adaptive_attack_uncertain_rate": adaptive_alert_rate,
        "adaptive_known_alert_rate": adaptive_known_fpr,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
