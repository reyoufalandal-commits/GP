#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def main() -> int:
    ap = argparse.ArgumentParser(description="Build before/after model quality iteration report.")
    ap.add_argument("--scorecard", default="reports/final_rare_scorecard.json")
    ap.add_argument("--kpi-policy", default="config/kpi_policy.json")
    ap.add_argument("--external-profiles", default="reports/unsw_external_profiles.json")
    ap.add_argument("--out", default="reports/quality_iteration_report.json")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    s = _load((root / args.scorecard).resolve())
    p = _load((root / args.kpi_policy).resolve())

    base_macro = float(s.get("train_compare", {}).get("base_macro_f1", 0.0))
    boost_macro = float(s.get("train_compare", {}).get("boost_macro_f1", 0.0))
    unknown_default = float(s.get("unsw_unknown_eval", {}).get("unknown_recall_attack_uncertain", 0.0))
    unknown_adaptive = float(s.get("unsw_unknown_eval", {}).get("adaptive_unknown_recall_attack_uncertain", 0.0))
    unknown_cal = float(s.get("unsw_novelty_calibrator_eval", {}).get("calibrator_unknown_recall", 0.0))
    known_alert_cal = float(s.get("unsw_novelty_calibrator_eval", {}).get("calibrator_known_alert_rate", 0.0))

    chosen_unknown = max(unknown_adaptive, unknown_cal)
    unknown_strategy = "adaptive_gates" if unknown_adaptive >= unknown_cal else "novelty_calibrator"

    profiles_path = (root / args.external_profiles).resolve()
    profiles = _load(profiles_path) if profiles_path.exists() else {}
    report = {
        "summary": {
            "macro_f1_before": base_macro,
            "macro_f1_after": boost_macro,
            "macro_f1_delta": boost_macro - base_macro,
            "unknown_recall_default": unknown_default,
            "unknown_recall_adaptive": unknown_adaptive,
            "unknown_recall_calibrator": unknown_cal,
            "selected_unknown_recall": chosen_unknown,
            "selected_unknown_strategy": unknown_strategy,
            "known_alert_rate_selected": known_alert_cal if unknown_strategy == "novelty_calibrator" else float(
                s.get("unsw_unknown_eval", {}).get("adaptive_known_alert_rate", 0.0)
            ),
        },
        "policy_targets": p,
        "recommendation": {
            "for_external_ood": unknown_strategy,
            "for_known_alert_budget": "novelty_calibrator",
            "for_holdout_internal": "p_attack_only_tuned_thresholds",
        },
        "external_profiles": {
            "balanced": profiles.get("balanced_profile"),
            "high_recall": profiles.get("high_recall_profile"),
        },
    }

    out = (root / args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
