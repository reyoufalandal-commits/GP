#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _safe_get(d: dict, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def main() -> int:
    ap = argparse.ArgumentParser(description="Build rare-class baseline summary from existing reports.")
    ap.add_argument("--metrics", default="reports/metrics_val_smoke.json")
    ap.add_argument("--triage-summary", default="reports/run_triage_summary.json")
    ap.add_argument("--out", default="reports/rare_baseline_report.json")
    args = ap.parse_args()

    metrics = json.loads(Path(args.metrics).read_text())
    tri = json.loads(Path(args.triage_summary).read_text())
    rep = metrics.get("classification_report", {})
    classes = []
    for k, v in rep.items():
        if k in ("accuracy", "macro avg", "weighted avg") or not isinstance(v, dict):
            continue
        classes.append(
            {
                "class": k,
                "f1": float(v.get("f1-score", 0.0)),
                "recall": float(v.get("recall", 0.0)),
                "precision": float(v.get("precision", 0.0)),
                "support": int(v.get("support", 0)),
            }
        )
    classes_sorted = sorted(classes, key=lambda x: x["f1"])
    out = {
        "accuracy": float(rep.get("accuracy", 0.0)),
        "macro_f1": float(_safe_get(rep, "macro avg", "f1-score", default=0.0)),
        "weighted_f1": float(_safe_get(rep, "weighted avg", "f1-score", default=0.0)),
        "lowest_f1_classes_top10": classes_sorted[:10],
        "triage_attack_uncertain": int(tri.get("decision_counts", {}).get("AttackUncertain", 0)),
        "triage_rows": int(tri.get("rows", 0)),
    }
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
