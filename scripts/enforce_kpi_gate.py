#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def evaluate_kpi_gate(
    scorecard: dict[str, Any],
    policy: dict[str, Any],
    *,
    rare_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    train_cmp = scorecard.get("train_compare", {})
    baseline = scorecard.get("baseline", {})
    unsw = scorecard.get("unsw_unknown_eval", {})
    cal = scorecard.get("unsw_novelty_calibrator_eval", {})

    macro_f1 = float(train_cmp.get("boost_macro_f1", 0.0))
    rare_floor = float(policy.get("rare_class_f1_min", 0.0))
    rare_classes = [str(x) for x in policy.get("rare_classes", [])]
    worst_rare_f1 = 1.0
    rare_map: dict[str, float] = {}
    if rare_metrics:
        rep = rare_metrics.get("classification_report", {})
        for c in rare_classes:
            if c in rep:
                rare_map[c] = float(rep[c].get("f1-score", 0.0))
    if not rare_map:
        rare_details = baseline.get("lowest_f1_classes_top10", [])
        rare_map = {str(x.get("class", "")): float(x.get("f1", 0.0)) for x in rare_details}
    for c in rare_classes:
        if c in rare_map:
            worst_rare_f1 = min(worst_rare_f1, rare_map[c])

    external_unknown_recall = max(
        float(unsw.get("adaptive_unknown_recall_attack_uncertain", 0.0)),
        float(cal.get("calibrator_unknown_recall", 0.0)),
    )
    known_alert_rate = float(cal.get("calibrator_known_alert_rate", 1.0))
    external_alert_rate = float(cal.get("calibrator_alert_rate", 1.0))

    checks = {
        "macro_f1": {
            "actual": macro_f1,
            "min": float(policy.get("macro_f1_min", 0.0)),
            "pass": macro_f1 >= float(policy.get("macro_f1_min", 0.0)),
        },
        "worst_rare_f1": {
            "actual": worst_rare_f1,
            "min": rare_floor,
            "pass": worst_rare_f1 >= rare_floor,
        },
        "external_unknown_recall": {
            "actual": external_unknown_recall,
            "min": float(policy.get("unknown_recall_external_min", 0.0)),
            "pass": external_unknown_recall >= float(policy.get("unknown_recall_external_min", 0.0)),
        },
        "known_alert_rate": {
            "actual": known_alert_rate,
            "max": float(policy.get("known_alert_rate_max", 1.0)),
            "pass": known_alert_rate <= float(policy.get("known_alert_rate_max", 1.0)),
        },
        "external_alert_rate": {
            "actual": external_alert_rate,
            "max": float(policy.get("max_alert_rate_external", 1.0)),
            "pass": external_alert_rate <= float(policy.get("max_alert_rate_external", 1.0)),
        },
    }
    return {"checks": checks, "passed": all(x["pass"] for x in checks.values())}


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate Hawk-Eye KPI policy gate from scorecard.")
    ap.add_argument("--scorecard", default="reports/final_rare_scorecard.json")
    ap.add_argument("--policy", default="config/kpi_policy.json")
    ap.add_argument("--rare-metrics", default="reports/metrics_rare_boost.json")
    ap.add_argument("--out", default="reports/kpi_gate.json")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    scorecard = _load_json((root / args.scorecard).resolve())
    policy = _load_json((root / args.policy).resolve())
    rare_metrics_path = (root / args.rare_metrics).resolve()
    rare_metrics = _load_json(rare_metrics_path) if rare_metrics_path.exists() else None
    payload = evaluate_kpi_gate(scorecard, policy, rare_metrics=rare_metrics)

    out = (root / args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
