#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate 2>/dev/null || true

TRAIN="${TRAIN_PATH:-data/processed/train.csv}"
VAL="${VAL_PATH:-data/processed/val.csv}"
LBL="${LABEL_COL:-Label}"
IDCOLS="${ID_COLS:-Flow ID,Source IP,Destination IP,Timestamp}"

BASE_BUNDLE="${BASE_BUNDLE:-artifacts/hawk-eye-sup-rare-base}"
BOOST_BUNDLE="${BOOST_BUNDLE:-artifacts/hawk-eye-sup-rare-boost}"

python3 -m hawk_eye.train \
  --data "${TRAIN}" --label-col "${LBL}" --id-cols "${IDCOLS}" \
  --dataset-slug rare-base --out "${BASE_BUNDLE}" --save-open-set-prototypes

python3 -m hawk_eye.evaluate \
  --data "${VAL}" --label-col "${LBL}" --model-dir "${BASE_BUNDLE}" \
  --out-metrics reports/metrics_rare_base.json

python3 -m hawk_eye.train \
  --data "${TRAIN}" --label-col "${LBL}" --id-cols "${IDCOLS}" \
  --dataset-slug rare-boost --out "${BOOST_BUNDLE}" \
  --model-type hist_gradient_boosting --logistic-balanced --rare-weight-power 0.7 \
  --save-open-set-prototypes

python3 -m hawk_eye.evaluate \
  --data "${VAL}" --label-col "${LBL}" --model-dir "${BOOST_BUNDLE}" \
  --out-metrics reports/metrics_rare_boost.json

python3 - <<'PY'
import json
from pathlib import Path
b=json.loads(Path('reports/metrics_rare_base.json').read_text())['classification_report']
r=json.loads(Path('reports/metrics_rare_boost.json').read_text())['classification_report']
out={
  'base_macro_f1': b['macro avg']['f1-score'],
  'boost_macro_f1': r['macro avg']['f1-score'],
  'delta_macro_f1': r['macro avg']['f1-score']-b['macro avg']['f1-score'],
  'base_accuracy': b['accuracy'],
  'boost_accuracy': r['accuracy'],
  'delta_accuracy': r['accuracy']-b['accuracy'],
}
Path('reports/rare_train_compare_summary.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
PY
