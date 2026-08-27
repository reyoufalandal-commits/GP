#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from hawk_eye.io import read_table


def main() -> int:
    ap = argparse.ArgumentParser(description="Run leave-family-out eval across top labels.")
    ap.add_argument("--data", required=True)
    ap.add_argument("--label-col", default="Label")
    ap.add_argument("--max-families", type=int, default=8)
    ap.add_argument("--out", default="reports/leave_family_out_matrix.json")
    args = ap.parse_args()

    df = read_table(args.data)
    vc = df[args.label_col].astype(str).value_counts()
    labels = [str(x) for x in vc.index[: int(args.max_families)]]
    runs = []
    for lab in labels:
        o = Path("reports") / f"leave_family_out_{lab.replace(' ', '_')}.json"
        cmd = [
            sys.executable,
            "scripts/eval_leave_family_out.py",
            "--data",
            args.data,
            "--label-col",
            args.label_col,
            "--holdout-label",
            lab,
            "--out",
            str(o),
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        runs.append(
            {
                "holdout_label": lab,
                "exit_code": int(p.returncode),
                "out": str(o),
                "stderr": p.stderr[-500:],
            }
        )

    payload = {"rows": len(df), "evaluated_labels": labels, "runs": runs}
    op = Path(args.out)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
