#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pandas as pd


def _copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> int:
    ap = argparse.ArgumentParser(description="Create isolated runtime-lab folder for realistic model testing.")
    ap.add_argument(
        "--lab-dir",
        default="../HawkEye_RuntimeLab",
        help="Destination lab folder (outside repo recommended).",
    )
    ap.add_argument(
        "--sample-rows",
        type=int,
        default=5000,
        help="Rows sampled from data/processed/val.csv into lab input.",
    )
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    lab = (root / args.lab_dir).resolve() if not str(args.lab_dir).startswith("/") else Path(args.lab_dir).resolve()

    (lab / "artifacts").mkdir(parents=True, exist_ok=True)
    (lab / "config").mkdir(parents=True, exist_ok=True)
    (lab / "input").mkdir(parents=True, exist_ok=True)
    (lab / "reports").mkdir(parents=True, exist_ok=True)
    (lab / "scripts").mkdir(parents=True, exist_ok=True)

    # Core bundles for standalone runtime behavior.
    for name in ["hawk-eye-binary", "hawk-eye-sup", "hawk-eye-anomaly-ae-tuned"]:
        src = root / "artifacts" / name
        if not src.exists():
            raise FileNotFoundError(f"Missing required artifact bundle: {src}")
        _copytree(src, lab / "artifacts" / name)

    # Optional RAG index and thresholds.
    rag_src = root / "artifacts" / "rag" / "rag_index.joblib"
    if rag_src.exists():
        _copy_file(rag_src, lab / "artifacts" / "rag" / "rag_index.joblib")
    thr_src = root / "reports" / "thresholds_fusion_selected.json"
    if thr_src.exists():
        _copy_file(thr_src, lab / "config" / "thresholds_fusion_selected.json")

    # Sample input from validation data.
    val_csv = root / "data" / "processed" / "val.csv"
    if not val_csv.exists():
        raise FileNotFoundError(f"Missing validation file for sample input: {val_csv}")
    df = pd.read_csv(val_csv)
    sample = df.head(int(args.sample_rows)).copy()
    if "Label" in sample.columns:
        sample = sample.drop(columns=["Label"])
    sample.to_parquet(lab / "input" / "test_flows.parquet", index=False)

    # Copy local runtime script into lab.
    _copy_file(root / "scripts" / "run_runtime_lab.py", lab / "scripts" / "run_runtime_lab.py")

    bootstrap = f"""#!/usr/bin/env bash
set -euo pipefail
LAB_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 -m venv "$LAB_DIR/.venv"
source "$LAB_DIR/.venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install -e "{root}"
python "$LAB_DIR/scripts/run_runtime_lab.py" --lab-dir "$LAB_DIR"
"""
    (lab / "bootstrap_and_run.sh").write_text(bootstrap)
    (lab / "bootstrap_and_run.sh").chmod(0o755)

    artifact_lock = {
        "binary_dir": "artifacts/hawk-eye-binary",
        "supervised_dir": "artifacts/hawk-eye-sup",
        "anomaly_dir": "artifacts/hawk-eye-anomaly-ae-tuned",
        "thresholds_file": "config/thresholds_fusion_selected.json",
        "rag_index": "artifacts/rag/rag_index.joblib",
    }
    (lab / "config" / "artifact_lock.json").write_text(json.dumps(artifact_lock, indent=2))

    summary = {
        "lab_dir": str(lab),
        "copied_artifacts": ["hawk-eye-binary", "hawk-eye-sup", "hawk-eye-anomaly-ae-tuned"],
        "sample_input_rows": int(len(sample)),
        "artifact_lock_file": str((lab / "config" / "artifact_lock.json").resolve()),
        "next_step": f"cd '{lab}' && ./bootstrap_and_run.sh",
    }
    (lab / "lab_manifest.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
