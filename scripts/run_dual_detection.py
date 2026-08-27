#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hawk_eye.live.dual_mode import run_batch_mode, run_stream_mode


def main() -> int:
    ap = argparse.ArgumentParser(description="Dual-mode detection: stream (Zeek) and batch (CSV/Parquet).")
    ap.add_argument("--mode", choices=["stream", "batch"], required=True)
    ap.add_argument("--binary-dir", default="artifacts/hawk-eye-binary")
    ap.add_argument("--supervised-dir", default="artifacts/hawk-eye-sup")
    ap.add_argument("--anomaly-dir", default="artifacts/hawk-eye-anomaly-ae-tuned")
    ap.add_argument("--thresholds-file", default="reports/thresholds_fusion_selected.json")
    ap.add_argument("--alert-log", default="reports/live_alerts.jsonl")
    ap.add_argument("--webhook-url", default=None)
    ap.add_argument("--emit-summary", default="reports/dual_mode_last_summary.json")

    ap.add_argument("--input", default=None, help="Batch input CSV/Parquet.")
    ap.add_argument("--output", default="reports/dual_mode_scored.parquet")
    ap.add_argument("--conn-log", default=None, help="Zeek conn.log path for stream mode.")
    ap.add_argument("--state-path", default="reports/live_stream_state.json")
    ap.add_argument("--poll-seconds", type=float, default=2.0)
    args = ap.parse_args()

    if args.mode == "batch":
        if not args.input:
            raise SystemExit("--input is required in batch mode.")
        summary = run_batch_mode(
            input_path=args.input,
            output_path=args.output,
            binary_dir=args.binary_dir,
            supervised_dir=args.supervised_dir,
            anomaly_dir=args.anomaly_dir,
            thresholds_file=args.thresholds_file,
            alert_log_path=args.alert_log,
            webhook_url=args.webhook_url,
        )
    else:
        if not args.conn_log:
            raise SystemExit("--conn-log is required in stream mode.")
        summary = run_stream_mode(
            conn_log=args.conn_log,
            state_path=args.state_path,
            output_path=args.output,
            binary_dir=args.binary_dir,
            supervised_dir=args.supervised_dir,
            anomaly_dir=args.anomaly_dir,
            thresholds_file=args.thresholds_file,
            alert_log_path=args.alert_log,
            webhook_url=args.webhook_url,
            poll_seconds=args.poll_seconds,
        )

    p = Path(args.emit_summary)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
