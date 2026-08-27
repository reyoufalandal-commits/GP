#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pandas as pd


KNOWN_LABELS = [
    "Benign",
    "DDoS",
    "FTP-Patator",
    "DoS slowloris",
    "PortScan",
    "Bot",
    "Web Attack � Brute Force",
]


def _run(cmd: list[str], root: Path) -> None:
    subprocess.run(cmd, cwd=root, check=True)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def main() -> int:
    ap = argparse.ArgumentParser(description="Run external-unknown pipeline using selected profile.")
    ap.add_argument("--profile", choices=["balanced", "high_recall"], required=True)
    ap.add_argument("--profiles-json", default="reports/unsw_external_profiles.json")
    ap.add_argument("--input", default="reports/unsw_scored_labeled.parquet")
    ap.add_argument("--binary-dir", default="artifacts/hawk-eye-binary")
    ap.add_argument("--supervised-dir", default="artifacts/hawk-eye-sup")
    ap.add_argument("--anomaly-dir", default="artifacts/hawk-eye-anomaly-ae-tuned")
    ap.add_argument("--calibrator-bundle", default="artifacts/novelty_calibrator_unsw")
    ap.add_argument("--out", default=None, help="Optional final summary path.")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    profiles = _load((root / args.profiles_json).resolve())
    selected = profiles[f"{args.profile}_profile"]
    out_path = (
        Path(args.out).resolve()
        if args.out
        else (root / "reports" / f"unsw_profile_{args.profile}_summary.json").resolve()
    )

    payload: dict[str, Any] = {"profile": args.profile, "selected": selected}
    if selected.get("method") == "adaptive":
        eval_out = (root / "reports" / f"unsw_unknown_eval_{args.profile}.json").resolve()
        df = pd.read_parquet((root / args.input).resolve()) if str(args.input).endswith(".parquet") else pd.read_csv(
            (root / args.input).resolve()
        )
        labels = df["Label"].astype(str)
        is_unknown = ~labels.isin(KNOWN_LABELS)
        is_known = ~is_unknown
        thr = selected["thresholds"]
        pred = (
            (df["suspected_zero_day_pct"] >= float(thr["suspected_zero_day_pct"]))
            | (df["anomaly_score"] >= float(thr["anomaly_score"]))
            | (df["open_set_ood_score"] >= float(thr["open_set_ood_score"]))
        )
        evaluation = {
            "rows": int(len(df)),
            "unknown_rows": int(is_unknown.sum()),
            "profile": "balanced",
            "attack_uncertain_rate": float(pred.mean()),
            "unknown_recall_attack_uncertain": float((pred & is_unknown).sum() / max(int(is_unknown.sum()), 1)),
            "known_alert_rate": float((pred & is_known).sum() / max(int(is_known.sum()), 1)),
            "thresholds": thr,
        }
        eval_out.write_text(json.dumps(evaluation, indent=2))
        payload["mode"] = "adaptive"
        payload["evaluation_file"] = str(eval_out)
        payload["evaluation"] = evaluation
    elif selected.get("method") == "calibrator":
        budget = float(selected["max_alert_budget"])
        fit_out = (root / "reports" / f"novelty_calibrator_unsw_fit_{args.profile}.json").resolve()
        apply_out = (root / "reports" / f"novelty_calibrator_unsw_apply_{args.profile}.json").resolve()
        scored_out = (root / "reports" / f"unsw_scored_with_calibrator_{args.profile}.parquet").resolve()
        eval_out = (root / "reports" / f"unsw_novelty_calibrator_eval_{args.profile}.json").resolve()

        cmd_fit = [
            sys.executable,
            "-m",
            "hawk_eye.novelty_calibrator",
            "fit",
            "--input",
            args.input,
            "--label-col",
            "Label",
            "--max-alert-rate",
            str(budget),
            "--out-dir",
            args.calibrator_bundle,
            "--out-summary",
            str(fit_out),
        ]
        for k in KNOWN_LABELS:
            cmd_fit.extend(["--known-label", k])
        _run(cmd_fit, root)

        cmd_apply = [
            sys.executable,
            "-m",
            "hawk_eye.novelty_calibrator",
            "apply",
            "--input",
            args.input,
            "--bundle-dir",
            args.calibrator_bundle,
            "--output",
            str(scored_out),
            "--out-summary",
            str(apply_out),
        ]
        _run(cmd_apply, root)

        cmd_eval = [
            sys.executable,
            "scripts/eval_unsw_novelty_calibrator.py",
            "--input",
            str(scored_out),
            "--label-col",
            "Label",
            "--out",
            str(eval_out),
        ]
        for k in KNOWN_LABELS:
            cmd_eval.extend(["--known-label", k])
        _run(cmd_eval, root)

        payload["mode"] = "calibrator"
        payload["fit_file"] = str(fit_out)
        payload["apply_file"] = str(apply_out)
        payload["evaluation_file"] = str(eval_out)
        payload["evaluation"] = _load(eval_out)
    else:
        raise ValueError(f"Unknown profile method: {selected.get('method')}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
