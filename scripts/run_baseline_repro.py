#!/usr/bin/env python3
from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

from hawk_eye.train import _build_pipeline


def _run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return p.stdout.strip()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = root / "reports" / "baseline" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    x_path = root / "tests" / "fixtures" / "sample_features.csv"
    y_path = root / "tests" / "fixtures" / "sample_labels.csv"
    X = pd.read_csv(x_path)
    y = pd.read_csv(y_path)["label"].to_numpy()

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    pipe = _build_pipeline(list(X.columns), logistic_class_weight=None)
    pipe.fit(X_tr, y_tr)
    pred = pipe.predict(X_te)

    metrics = {
        "rows_total": int(len(X)),
        "rows_train": int(len(X_tr)),
        "rows_test": int(len(X_te)),
        "accuracy": float(accuracy_score(y_te, pred)),
        "f1_macro": float(f1_score(y_te, pred, average="macro", zero_division=0)),
        "labels_present": sorted(str(x) for x in np.unique(y)),
    }

    env = {
        "python": sys.version,
        "platform": platform.platform(),
        "utc_generated_at": ts,
    }
    try:
        env["pip_freeze"] = _run([sys.executable, "-m", "pip", "freeze"]).splitlines()
    except Exception:
        env["pip_freeze"] = []

    (out_dir / "baseline_metrics.json").write_text(json.dumps(metrics, indent=2))
    (out_dir / "environment.json").write_text(json.dumps(env, indent=2))
    latest = root / "reports" / "baseline" / "latest.json"
    latest.write_text(
        json.dumps(
            {
                "run_dir": str(out_dir.resolve()),
                "metrics_file": str((out_dir / "baseline_metrics.json").resolve()),
                "environment_file": str((out_dir / "environment.json").resolve()),
            },
            indent=2,
        )
    )
    print(json.dumps({"run_dir": str(out_dir.resolve()), **metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
