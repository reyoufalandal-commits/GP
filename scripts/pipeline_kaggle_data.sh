#!/usr/bin/env bash
# Train on Parquet/CSV files under kaggleData/ (or set RAW_DIR).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RAW_DIR="${RAW_DIR:-kaggleData}"
LABEL_COL="${LABEL_COL:-Label}"
# Cap rows for manageable RAM/time on laptop (raise or remove for full dataset)
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

BUNDLE="artifacts/hawk-eye-kaggle-$(date +%Y%m%d-%H%M)"
echo "==> Training → ${BUNDLE}"
# no-metadata Parquet has no Flow/IP columns — numeric features + Label only
python3 -m hawk_eye.train \
  --data data/processed/train.csv \
  --label-col "${LABEL_COL}" \
  --id-cols "" \
  --dataset-slug "local/kaggleData" \
  --out "${BUNDLE}"

ln -sfn "$(basename "${BUNDLE}")" artifacts/current

mkdir -p reports
python3 -m hawk_eye.evaluate \
  --data data/processed/val.csv \
  --label-col "${LABEL_COL}" \
  --model-dir "${BUNDLE}" \
  --out-metrics reports/metrics_val_kaggle.json

echo "Done. Bundle: ${BUNDLE}  (artifacts/current)"
