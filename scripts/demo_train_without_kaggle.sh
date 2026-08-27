#!/usr/bin/env bash
# Train end-to-end on a tiny synthetic CSV (no Kaggle). Use this to verify the pipeline before downloading CICIDS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DEMO_DIR="data/raw/local_demo"
mkdir -p "${DEMO_DIR}"

python3 << 'PY'
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(42)
n = 500
df = pd.DataFrame({
    "Flow ID": [f"f{i}" for i in range(n)],
    "Source IP": ["10.0.0.1"] * n,
    "Destination IP": ["10.0.0.2"] * n,
    "Timestamp": np.arange(n),
    "Destination Port": rng.integers(1, 65535, size=n),
    "Flow Duration": rng.integers(1, 100000, size=n),
    "Total Fwd Packets": rng.integers(1, 500, size=n),
    "Total Backward Packets": rng.integers(1, 500, size=n),
    "Label": rng.choice(["BENIGN", "DoS"], size=n, p=[0.7, 0.3]),
})
out = Path("data/raw/local_demo/demo_flows.csv")
out.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(out, index=False)
print(f"Wrote {out} rows={len(df)}")
PY

python3 scripts/build_splits.py \
  --raw-dir "${DEMO_DIR}" \
  --dataset-slug "local/demo" \
  --label-col Label \
  --out-dir data/processed \
  --interim data/interim/merged_demo.csv

BUNDLE="artifacts/hawk-eye-demo-local"
python3 -m hawk_eye.train \
  --data data/processed/train.csv \
  --label-col Label \
  --id-cols "Flow ID,Source IP,Destination IP,Timestamp" \
  --dataset-slug "local/demo" \
  --out "${BUNDLE}"

ln -sfn "$(basename "${BUNDLE}")" artifacts/current
python3 -m hawk_eye.evaluate \
  --data data/processed/val.csv \
  --label-col Label \
  --model-dir "${BUNDLE}" \
  --out-metrics reports/metrics_demo.json

echo "Demo OK. Bundle: ${BUNDLE}"
