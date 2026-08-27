#!/usr/bin/env bash
# High-recall suspected zero-day: flag on benign-trained anomaly score only (use bundle threshold).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate 2>/dev/null || true

PROCESSED="${PROCESSED_DIR:-data/processed}"
AE_OUT="${ANOMALY_AE_BUNDLE:-artifacts/hawk-eye-anomaly-ae-tuned}"

python3 -m hawk_eye.detect_novel \
  --input "${PROCESSED}/val.csv" \
  --output reports/novel_scored_anomaly_only.parquet \
  --supervised-dir "${SUPERVISED_DIR:-artifacts/current}" \
  --anomaly-dir "${AE_OUT}" \
  --novel-label Suspected_ZeroDay \
  --no-require-low-confidence

echo "Wrote reports/novel_scored_anomaly_only.parquet"
