#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()[:80]


def main() -> int:
    ap = argparse.ArgumentParser(description="Run LFO threshold tuning for multiple holdout families.")
    ap.add_argument("--train", default="data/processed/train.csv")
    ap.add_argument("--val", default="data/processed/val.csv")
    ap.add_argument("--label-col", default="Label")
    ap.add_argument("--binary-dir", default="artifacts/hawk-eye-binary")
    ap.add_argument("--anomaly-dir", default="artifacts/hawk-eye-anomaly-ae-tuned")
    ap.add_argument("--max-alert-rate", type=float, default=0.10)
    ap.add_argument("--max-families", type=int, default=4)
    ap.add_argument("--out", default="reports/holdout_multi_thresholds.json")
    args = ap.parse_args()

    tr = pd.read_csv(args.train, usecols=[args.label_col])
    counts = tr[args.label_col].astype(str).value_counts()
    holds = [x for x in counts.index.tolist() if str(x).strip().lower() != "benign"][: int(args.max_families)]
    val_labels = pd.read_csv(args.val, usecols=[args.label_col])

    recs = []
    for hold in holds:
        hs = _slug(hold)
        train_df = pd.read_csv(args.train)
        train_lfo = train_df[train_df[args.label_col].astype(str) != str(hold)].copy()
        train_lfo_path = Path("data/processed") / f"train_lfo_{hs}.csv"
        train_lfo.to_csv(train_lfo_path, index=False)
        sup_dir = Path("artifacts") / f"hawk-eye-sup-lfo-{hs}"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "hawk_eye.train",
                "--data",
                str(train_lfo_path),
                "--label-col",
                args.label_col,
                "--id-cols",
                "Flow ID,Source IP,Destination IP,Timestamp",
                "--dataset-slug",
                f"lfo-{hs}",
                "--out",
                str(sup_dir),
                "--save-open-set-prototypes",
            ],
            check=True,
        )
        out_attack = Path("reports") / f"attack_uncertain_lfo_{hs}.parquet"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "hawk_eye.detect_attack_uncertain",
                "--input",
                args.val,
                "--output",
                str(out_attack),
                "--binary-dir",
                args.binary_dir,
                "--supervised-dir",
                str(sup_dir),
                "--anomaly-dir",
                args.anomaly_dir,
            ],
            check=True,
        )
        out_open = Path("reports") / f"open_set_lfo_{hs}.parquet"
        subprocess.run(
            [sys.executable, "-m", "hawk_eye.open_set", "--input", args.val, "--output", str(out_open), "--model-dir", str(sup_dir)],
            check=True,
        )
        left = pd.read_parquet(out_attack).reset_index(drop=True)
        right = pd.read_parquet(out_open)[["open_set_nearest_distance", "open_set_ood_score"]].reset_index(drop=True)
        merged = pd.concat([val_labels.reset_index(drop=True), left, right], axis=1)
        merged_path = Path("reports") / f"triage_lfo_{hs}_labeled.parquet"
        merged.to_parquet(merged_path, index=False)

        known_labels = sorted(set(train_lfo[args.label_col].astype(str)))
        cmd = [
            str(Path("scripts/eval_unknown_budget.py")),
            "--input",
            str(merged_path),
            "--label-col",
            args.label_col,
            "--max-alert-rate",
            str(float(args.max_alert_rate)),
            "--out",
            str(Path("reports") / f"thresholds_lfo_{hs}.json"),
        ]
        for k in known_labels:
            cmd += ["--known-label", k]
        subprocess.run(cmd, check=True)
        rec = json.loads((Path("reports") / f"thresholds_lfo_{hs}.json").read_text())["recommendation"]
        recs.append({"holdout": hold, "slug": hs, "recommendation": rec})

    usable = [r for r in recs if r["recommendation"].get("unknown_recall", 0) > 0]
    if usable:
        sel = max(usable, key=lambda x: x["recommendation"]["unknown_recall"])
        best = sel["recommendation"]
    else:
        best = {"p_attack_threshold": 0.7, "szd_threshold": 70.0, "open_set_threshold": 0.6}
    fusion = {
        "min_p_attack_known": max(0.70, float(best.get("p_attack_threshold", 0.70)) + 0.10),
        "min_szd_uncertain": 70.0 if best.get("szd_threshold") is None else float(best.get("szd_threshold")),
        "min_open_set_uncertain": 0.60 if best.get("open_set_threshold") is None else float(best.get("open_set_threshold")),
        "source": "holdout_multi_family_best",
    }
    Path("reports/thresholds_fusion_selected.json").write_text(json.dumps(fusion, indent=2))
    out = {"holdouts": holds, "results": recs, "selected_fusion_thresholds": fusion}
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
