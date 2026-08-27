#!/usr/bin/env bash
# PCAP directory → CICFlowMeter (optional) → normalize → validate (template).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PCAP_INPUT="${1:?Usage: $0 <pcap_dir_or_file> [output_csv_basename]}"

BASE="${2:-data/interim/live_cicflow}"
RAW_CSV="${BASE}.csv"
NORM_CSV="${BASE}_normalized.csv"

if [[ -z "${CICFLOWMETER_JAR:-}" ]]; then
  echo "Set CICFLOWMETER_JAR to your CICFlowMeter JAR path."
  echo "Example: export CICFLOWMETER_JAR=\$HOME/tools/CICFlowMeter/CICFlowMeter.jar"
  echo "Then run your Java command manually; many CICFlowMeter builds use:"
  echo "  java -jar \"\$CICFLOWMETER_JAR\" \"<pcap_dir>\" \"<out_csv>\""
  echo "See docs/cic_live_pipeline.md"
  exit 2
fi

echo "==> Running CICFlowMeter → ${RAW_CSV}"
if [[ ! -f "${CICFLOWMETER_JAR}" ]]; then
  echo "ERROR: JAR not found: ${CICFLOWMETER_JAR}"
  exit 2
fi

# Common pattern: CICFlowMeter <pcap_dir> <output_csv> — adjust if your build differs.
java -jar "${CICFLOWMETER_JAR}" "${PCAP_INPUT}" "${RAW_CSV}"

echo "==> Normalizing columns → ${NORM_CSV}"
python3 scripts/normalize_flow_csv.py \
  --input "${RAW_CSV}" \
  --output "${NORM_CSV}" \
  --model-dir "${MODEL_DIR:-artifacts/current}"

echo "==> Validating schema"
python3 scripts/validate_feature_schema.py --input "${NORM_CSV}" --model-dir "${MODEL_DIR:-artifacts/current}"

echo "Done. Next: python3 -m hawk_eye.score --input ${NORM_CSV} --output scored.parquet --predictions --proba-all"
