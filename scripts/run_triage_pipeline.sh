#!/usr/bin/env bash
# End-to-end triage labels: KnownAttack / AttackUncertain / BenignOrLowRisk
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate 2>/dev/null || true

PROCESSED="${PROCESSED_DIR:-data/processed}"
INPUT="${INPUT_PATH:-${PROCESSED}/val.csv}"
BIN="${HAWK_EYE_BINARY_DIR:-artifacts/hawk-eye-binary}"
SUP="${SUPERVISED_DIR:-artifacts/hawk-eye-sup}"
ANOM="${ANOMALY_AE_BUNDLE:-artifacts/hawk-eye-anomaly-ae-tuned}"

mkdir -p reports

python3 -m hawk_eye.detect_attack_uncertain \
  --input "${INPUT}" \
  --output reports/attack_uncertain_scored.parquet \
  --binary-dir "${BIN}" \
  --supervised-dir "${SUP}" \
  --anomaly-dir "${ANOM}" \
  --emit-run-summary reports/run_attack_uncertain_summary.json

OPEN_SET_PROTO="${SUP}/open_set_prototypes.npz"
if [[ -f "${OPEN_SET_PROTO}" ]]; then
  python3 -m hawk_eye.open_set \
    --input "${INPUT}" \
    --output reports/open_set_scored.parquet \
    --model-dir "${SUP}"

  python3 - <<'PY'
import pandas as pd
left = pd.read_parquet("reports/attack_uncertain_scored.parquet").reset_index(drop=True)
right = pd.read_parquet("reports/open_set_scored.parquet")[["open_set_nearest_distance", "open_set_ood_score"]].reset_index(drop=True)
out = pd.concat([left, right], axis=1)
out.to_parquet("reports/attack_uncertain_with_open_set.parquet", index=False)
print({"rows": len(out), "output": "reports/attack_uncertain_with_open_set.parquet"})
PY
  FUSION_INPUT="reports/attack_uncertain_with_open_set.parquet"
else
  echo "No open-set prototypes at ${OPEN_SET_PROTO}; fusing without open_set_ood_score."
  FUSION_INPUT="reports/attack_uncertain_scored.parquet"
fi

python3 -m hawk_eye.decision_fusion \
  --input "${FUSION_INPUT}" \
  --output reports/triage_decisions.parquet \
  $(if [[ -f reports/thresholds_fusion_selected.json ]]; then echo "--thresholds-file reports/thresholds_fusion_selected.json"; fi) \
  --emit-run-summary reports/run_triage_summary.json

echo "Wrote reports/triage_decisions.parquet"
