#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _j(path: str, default: dict | None = None) -> dict:
    p = Path(path)
    if not p.exists():
        return {} if default is None else default
    return json.loads(p.read_text())


def main() -> int:
    ap = argparse.ArgumentParser(description="Final scorecard for rare-class + unknown novelty improvement.")
    ap.add_argument("--baseline", default="reports/rare_baseline_report.json")
    ap.add_argument("--train-compare", default="reports/rare_train_compare_summary.json")
    ap.add_argument("--holdout", default="reports/holdout_multi_thresholds.json")
    ap.add_argument("--unsw", default="reports/unsw_unknown_eval.json")
    ap.add_argument("--unsw-calibrator", default="reports/unsw_novelty_calibrator_eval.json")
    ap.add_argument("--out", default="reports/final_rare_scorecard.json")
    args = ap.parse_args()

    b = _j(args.baseline)
    t = _j(args.train_compare)
    h = _j(args.holdout)
    u = _j(args.unsw)
    uc = _j(args.unsw_calibrator)

    score = 0.0
    if t.get("delta_macro_f1", 0) > 0:
        score += 4.0
    if h.get("selected_fusion_thresholds"):
        score += 3.0
    if u.get("unknown_recall_attack_uncertain", 0) > 0.1:
        score += 3.0
    if uc.get("calibrator_unknown_recall", 0) > max(0.1, u.get("unknown_recall_attack_uncertain", 0)):
        score += 1.0

    payload = {
        "baseline": b,
        "train_compare": t,
        "holdout_multi": h,
        "unsw_unknown_eval": u,
        "unsw_novelty_calibrator_eval": uc,
        "overall_improvement_score_10": round(score, 2),
    }
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
