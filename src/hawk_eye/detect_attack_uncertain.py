"""
CLI: binary Attack + multiclass/anomaly novelty signals → ``is_attack_uncertain`` triage column.

See :func:`hawk_eye.detect_novel.attack_uncertain_dataframe`.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np

from hawk_eye.detect_novel import attack_uncertain_dataframe
from hawk_eye.io import read_table, write_table


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Flag rows where the binary model predicts Attack AND "
            "(novelty heuristic OR high suspected_zero_day_pct). "
            "Use with multiclass + benign-trained anomaly bundles."
        )
    )
    ap.add_argument("--input", required=True, help="CSV/Parquet with same features as all bundles.")
    ap.add_argument("--output", required=True, help="Output CSV/Parquet with diagnostics + is_attack_uncertain.")
    ap.add_argument(
        "--binary-dir",
        default=None,
        help="Binary Benign-vs-Attack bundle (default HAWK_EYE_BINARY_DIR or set env).",
    )
    ap.add_argument("--supervised-dir", default=None, help="Multiclass supervised bundle.")
    ap.add_argument("--anomaly-dir", default=None, help="Benign-only anomaly bundle.")
    ap.add_argument("--novel-label", default="Suspected_ZeroDay")
    ap.add_argument("--confidence-threshold", type=float, default=0.55)
    ap.add_argument("--anomaly-threshold", type=float, default=None)
    ap.add_argument("--no-require-low-confidence", action="store_true")
    ap.add_argument("--tier-strong-label", default=None)
    ap.add_argument("--tier-percentile", type=float, default=90.0)
    ap.add_argument("--risk-weight-anomaly", type=float, default=0.5)
    ap.add_argument("--risk-weight-uncertainty", type=float, default=0.5)
    ap.add_argument("--softmax-temperature", type=float, default=1.0)
    ap.add_argument("--risk-scale-ref", default=None)
    ap.add_argument(
        "--min-szd-pct-for-attack-uncertain",
        type=float,
        default=70.0,
        help="Binary Attack + suspected_zero_day_pct >= this also counts as attack-uncertain.",
    )
    ap.add_argument("--emit-run-summary", default=None)
    args = ap.parse_args()

    df = read_table(args.input)
    risk_ref = None
    if args.risk_scale_ref:
        ref_df = read_table(args.risk_scale_ref)
        if "anomaly_score" not in ref_df.columns:
            raise ValueError("--risk-scale-ref must contain column 'anomaly_score'")
        risk_ref = ref_df["anomaly_score"].to_numpy(dtype=np.float64)

    binary_dir = args.binary_dir or os.environ.get("HAWK_EYE_BINARY_DIR")
    if not binary_dir:
        raise SystemExit(
            "Set --binary-dir or export HAWK_EYE_BINARY_DIR to your trained binary bundle."
        )

    out = attack_uncertain_dataframe(
        df,
        binary_dir=binary_dir,
        supervised_dir=args.supervised_dir,
        anomaly_dir=args.anomaly_dir,
        novel_label=args.novel_label,
        confidence_threshold=args.confidence_threshold,
        anomaly_threshold=args.anomaly_threshold,
        require_low_confidence=not args.no_require_low_confidence,
        tier_strong_label=args.tier_strong_label,
        tier_percentile=args.tier_percentile,
        risk_weight_anomaly=args.risk_weight_anomaly,
        risk_weight_uncertainty=args.risk_weight_uncertainty,
        softmax_temperature=args.softmax_temperature,
        risk_ref_anomaly_scores=risk_ref,
        min_szd_pct_for_attack_uncertain=args.min_szd_pct_for_attack_uncertain,
    )
    write_table(out, args.output)

    n_unc = int(out["is_attack_uncertain"].sum())
    n_novel = int(out["is_novel_flagged"].sum())
    summary: dict[str, Any] = {
        "rows": len(out),
        "attack_uncertain": n_unc,
        "novel_flagged": n_novel,
        "novel_label": args.novel_label,
        "output": str(Path(args.output).resolve()),
    }
    sp = out["suspected_zero_day_pct"]
    summary["suspected_zero_day_pct_median"] = float(np.median(sp))
    summary["anomaly_score_p99"] = float(np.percentile(out["anomaly_score"], 99.0))
    if args.emit_run_summary:
        Path(args.emit_run_summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.emit_run_summary).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
