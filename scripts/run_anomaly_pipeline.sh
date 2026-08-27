#!/usr/bin/env bash
# Phase A–D: export benign splits → train Isolation Forest anomaly model → evaluate on val → symlink current_anomaly
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate 2>/dev/null || true

PROCESSED="${PROCESSED_DIR:-data/processed}"
OUT="${ANOMALY_BUNDLE:-artifacts/hawk-eye-anomaly-$(date +%Y%m%d-%H%M)}"

echo "==> Export benign-only from ${PROCESSED}"
python3 -m hawk_eye.export_benign --processed-dir "${PROCESSED}"

echo "==> Train anomaly (Isolation Forest)"
python3 -m hawk_eye.train_anomaly \
  --mode iforest \
  --benign-train "${PROCESSED}/benign_train.csv" \
  --benign-val "${PROCESSED}/benign_val.csv" \
  --label-col Label \
  --out "${OUT}"

ln -sfn "$(basename "${OUT}")" artifacts/current_anomaly

echo "==> Evaluate on full validation split (benign + attacks)"
python3 -m hawk_eye.evaluate_anomaly \
  --data "${PROCESSED}/val.csv" \
  --label-col Label \
  --model-dir "${OUT}" \
  --out-metrics reports/metrics_anomaly_val.json

echo "Done. Anomaly bundle: ${OUT}  (artifacts/current_anomaly)"
