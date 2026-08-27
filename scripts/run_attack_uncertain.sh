#!/usr/bin/env bash
# Binary Attack + multiclass/anomaly: column is_attack_uncertain (triage "attack but suspicious").
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate 2>/dev/null || true

PROCESSED="${PROCESSED_DIR:-data/processed}"
BIN="${HAWK_EYE_BINARY_DIR:-artifacts/hawk-eye-binary}"
SUP="${SUPERVISED_DIR:-artifacts/hawk-eye-sup}"
AE_OUT="${ANOMALY_AE_BUNDLE:-artifacts/hawk-eye-anomaly-ae-tuned}"

python3 -m hawk_eye.detect_attack_uncertain \
  --input "${PROCESSED}/val.csv" \
  --output reports/attack_uncertain_scored.parquet \
  --binary-dir "${BIN}" \
  --supervised-dir "${SUP}" \
  --anomaly-dir "${AE_OUT}" \
  --novel-label Suspected_ZeroDay \
  --min-szd-pct-for-attack-uncertain 70

echo "Wrote reports/attack_uncertain_scored.parquet (filter: is_attack_uncertain == True)"
