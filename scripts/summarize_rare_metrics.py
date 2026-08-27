#!/usr/bin/env python3
"""Read hawk_eye.evaluate JSON and print rare / low-F1 classes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metrics", required=True, help="metrics_val_*.json from evaluate")
    ap.add_argument("--top-low-f1", type=int, default=15)
    args = ap.parse_args()
    data = json.loads(Path(args.metrics).read_text())
    rep = data.get("classification_report", {})
    rows: list[tuple[str, float, float, float]] = []
    for k, v in rep.items():
        if k in ("accuracy", "macro avg", "weighted avg") or not isinstance(v, dict):
            continue
        rows.append(
            (
                k,
                float(v.get("f1-score", 0)),
                float(v.get("support", 0)),
                float(v.get("recall", 0)),
            )
        )
    rows.sort(key=lambda x: (x[1], x[2]))
    print(f"Lowest F1 (up to {args.top_low_f1} classes):\n")
    for name, f1, sup, rec in rows[: args.top_low_f1]:
        print(f"  {name}: F1={f1:.4f}  recall={rec:.4f}  support={int(sup)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
