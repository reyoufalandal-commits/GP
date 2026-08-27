#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate 2>/dev/null || true

IN="${INPUT_PATH:-reports/unsw_scored_labeled.parquet}"
BUNDLE="${BUNDLE_DIR:-artifacts/novelty_calibrator_unsw}"
MAX_ALERT="${MAX_ALERT_RATE:-0.10}"

python3 -m hawk_eye.novelty_calibrator fit \
  --input "${IN}" \
  --label-col Label \
  --known-label Benign \
  --known-label DDoS \
  --known-label FTP-Patator \
  --known-label "DoS slowloris" \
  --known-label PortScan \
  --known-label "Web Attack � Brute Force" \
  --known-label Bot \
  --max-alert-rate "${MAX_ALERT}" \
  --out-dir "${BUNDLE}" \
  --out-summary reports/novelty_calibrator_unsw_fit.json

python3 -m hawk_eye.novelty_calibrator apply \
  --input "${IN}" \
  --bundle-dir "${BUNDLE}" \
  --output reports/unsw_scored_with_calibrator.parquet \
  --out-summary reports/novelty_calibrator_unsw_apply.json

echo "Wrote calibrator bundle: ${BUNDLE}"
