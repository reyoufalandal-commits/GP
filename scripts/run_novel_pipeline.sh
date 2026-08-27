#!/usr/bin/env bash
# End-to-end: export benign → train AE anomaly (tuned) → evaluate → optional detect_novel
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate 2>/dev/null || true

PROCESSED="${PROCESSED_DIR:-data/processed}"
AE_OUT="${ANOMALY_AE_BUNDLE:-artifacts/hawk-eye-anomaly-ae-tuned}"
EPOCHS="${AE_EPOCHS:-12}"
PERC="${AE_PERCENTILE:-97.5}"

echo "==> 1) Export benign splits"
python3 -m hawk_eye.export_benign --processed-dir "${PROCESSED}"

echo "==> 2) Train autoencoder anomaly (percentile=${PERC} → more attack recall vs 99.0)"
python3 -m hawk_eye.train_anomaly \
  --mode ae \
  --benign-train "${PROCESSED}/benign_train.csv" \
  --benign-val "${PROCESSED}/benign_val.csv" \
  --label-col Label \
  --out "${AE_OUT}" \
  --epochs "${EPOCHS}" \
  --batch-size 4096 \
  --percentile "${PERC}" \
  --ae-hidden 128,64 \
  --ae-latent 32

ln -sfn "$(basename "${AE_OUT}")" artifacts/current_anomaly

echo "==> 3) Evaluate anomaly on full val (benign + attack)"
mkdir -p reports
python3 -m hawk_eye.evaluate_anomaly \
  --data "${PROCESSED}/val.csv" \
  --label-col Label \
  --model-dir "${AE_OUT}" \
  --out-metrics reports/metrics_anomaly_val_ae_tuned.json

echo "==> 4) detect_novel (combo: uncertain supervised + high anomaly) — tune CONFIDENCE (0.85–0.95 typical)"
CONF="${NOVEL_CONFIDENCE:-0.90}"
python3 -m hawk_eye.detect_novel \
  --input "${PROCESSED}/val.csv" \
  --output reports/novel_scored_val.parquet \
  --supervised-dir "${SUPERVISED_DIR:-artifacts/current}" \
  --anomaly-dir "${AE_OUT}" \
  --novel-label Suspected_ZeroDay \
  --confidence-threshold "${CONF}"

echo ""
echo "Optional: anomaly-only rule (more Suspected_ZeroDay rows, more FPs):"
echo "  NOVEL_MODE=anomaly_only ./scripts/run_novel_detect_only.sh"
echo "Done. Anomaly metrics: reports/metrics_anomaly_val_ae_tuned.json"
