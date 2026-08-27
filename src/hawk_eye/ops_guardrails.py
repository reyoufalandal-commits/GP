from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from hawk_eye.io import read_table
from hawk_eye.redact import redact_obj


def write_audit_event(event_type: str, payload: dict[str, Any]) -> Path:
    p = Path(os.environ.get("HAWK_EYE_AUDIT_LOG", "reports/audit/events.jsonl"))
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": int(time.time()), "event_type": event_type, "payload": redact_obj(payload)}
    with p.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    return p


def summarize_operational_health(
    df_path: str | Path,
    *,
    decision_col: str = "decision_label",
    max_attack_uncertain_rate: float = 0.25,
) -> dict[str, Any]:
    df = read_table(df_path)
    if decision_col not in df.columns:
        raise ValueError(f"Missing decision column: {decision_col}")
    counts = df[decision_col].astype(str).value_counts().to_dict()
    total = max(int(len(df)), 1)
    uncertain = int(counts.get("AttackUncertain", 0))
    uncertain_rate = uncertain / total
    healthy = uncertain_rate <= float(max_attack_uncertain_rate)
    return {
        "rows": int(len(df)),
        "decision_counts": counts,
        "attack_uncertain_rate": float(uncertain_rate),
        "max_attack_uncertain_rate": float(max_attack_uncertain_rate),
        "healthy": bool(healthy),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Operational health + audit helper.")
    ap.add_argument("--input", required=True, help="Triaged CSV/Parquet.")
    ap.add_argument("--output", default="reports/ops/health_summary.json")
    ap.add_argument("--max-attack-uncertain-rate", type=float, default=0.25)
    args = ap.parse_args()

    out = summarize_operational_health(
        args.input,
        max_attack_uncertain_rate=float(args.max_attack_uncertain_rate),
    )
    op = Path(args.output)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(out, indent=2))
    write_audit_event("operational_health_summary", out)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
