#!/usr/bin/env python3
"""Write a structured drift report to reports/drift_report.json for dashboards and governance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hawk_eye.backend.detection_resolution import project_root
from hawk_eye.drift_compare import build_drift_report_payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference", required=True)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--columns", default="", help="Comma-separated; empty = numeric intersection.")
    ap.add_argument("--out", default=None, help="Default: reports/drift_report.json under repo root.")
    args = ap.parse_args()
    cols = [c.strip() for c in args.columns.split(",") if c.strip()] if args.columns.strip() else None
    payload = build_drift_report_payload(
        reference=args.reference,
        sample=args.sample,
        columns=cols,
    )
    out = Path(args.out) if args.out else project_root() / "reports" / "drift_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps({"ok": True, "path": str(out.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
