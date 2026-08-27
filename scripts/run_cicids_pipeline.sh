#!/usr/bin/env bash
# Full path: download (Kaggle) → merge/split → train → optional symlink artifacts/current
# Requires: ~/.kaggle/kaggle.json and: pip install -r requirements.txt && pip install -e .
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SLUG="${KAGGLE_SLUG:-dhoogla/cicids2017}"
RAW_DIR="data/raw/${SLUG//\//__}"
LABEL_COL="${LABEL_COL:-Label}"
MAX_ROWS="${MAX_ROWS:-200000}"

if [[ ! -f "${HOME}/.kaggle/kaggle.json" ]]; then
  echo "ERROR: Missing ~/.kaggle/kaggle.json"
  echo "Create it: Kaggle → Account → API → Create New API Token → save as ~/.kaggle/kaggle.json"
  echo "Then: chmod 600 ~/.kaggle/kaggle.json"
  exit 2
fi

echo "==> Downloading ${SLUG} to ${RAW_DIR}"
./scripts/download_data.sh "${SLUG}"

echo "==> Building splits (label=${LABEL_COL}, max_rows=${MAX_ROWS})"
python3 scripts/build_splits.py \
  --raw-dir "${RAW_DIR}" \
  --dataset-slug "${SLUG}" \
  --label-col "${LABEL_COL}" \
  --out-dir data/processed \
  --interim data/interim/merged.csv \
  --max-rows "${MAX_ROWS}"

BUNDLE="artifacts/hawk-eye-cicids-$(date +%Y%m%d-%H%M)"
echo "==> Training → ${BUNDLE}"
python3 -m hawk_eye.train \
  --data data/processed/train.csv \
  --label-col "${LABEL_COL}" \
  --id-cols "Flow ID,Source IP,Destination IP,Timestamp" \
  --dataset-slug "${SLUG}" \
  --out "${BUNDLE}" \
  --save-open-set-prototypes

ln -sfn "$(basename "${BUNDLE}")" artifacts/current
echo "==> artifacts/current -> ${BUNDLE}"

echo "==> Evaluate on val set"
python3 -m hawk_eye.evaluate \
  --data data/processed/val.csv \
  --label-col "${LABEL_COL}" \
  --model-dir "${BUNDLE}" \
  --out-metrics reports/metrics_val.json

echo "Done. Bundle: ${BUNDLE}"
