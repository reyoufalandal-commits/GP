#!/usr/bin/env bash
# Train PyTorch MLP on Parquet under kaggleData/ (same splits as pipeline_kaggle_data.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RAW_DIR="${RAW_DIR:-kaggleData}"
LABEL_COL="${LABEL_COL:-Label}"
MAX_ROWS="${MAX_ROWS:-400000}"

if [[ ! -d "${RAW_DIR}" ]]; then
  echo "ERROR: Directory not found: ${RAW_DIR}"
  exit 2
fi

echo "==> Merging + splitting from ${RAW_DIR} (max_rows=${MAX_ROWS})"
python3 scripts/build_splits.py \
  --raw-dir "${RAW_DIR}" \
  --dataset-slug "local/kaggleData" \
  --label-col "${LABEL_COL}" \
  --out-dir data/processed \
  --interim data/interim/merged_kaggle.parquet \
  --max-rows "${MAX_ROWS}"

BUNDLE="artifacts/hawk-eye-torch-$(date +%Y%m%d-%H%M)"
echo "==> PyTorch training → ${BUNDLE}"
python3 -m hawk_eye.train_torch \
  --data data/processed/train.csv \
  --val-data data/processed/val.csv \
  --label-col "${LABEL_COL}" \
  --id-cols "" \
  --dataset-slug "local/kaggleData" \
  --epochs "${EPOCHS:-30}" \
  --batch-size "${BATCH_SIZE:-1024}" \
  --class-weight balanced \
  --early-stopping-patience "${EARLY_STOP_PATIENCE:-5}" \
  --out "${BUNDLE}"

ln -sfn "$(basename "${BUNDLE}")" artifacts/current

mkdir -p reports
python3 -m hawk_eye.evaluate \
  --data data/processed/val.csv \
  --label-col "${LABEL_COL}" \
  --model-dir "${BUNDLE}" \
  --out-metrics reports/metrics_val_kaggle_torch.json

echo "Done. Bundle: ${BUNDLE}  (artifacts/current)  metrics: reports/metrics_val_kaggle_torch.json"
