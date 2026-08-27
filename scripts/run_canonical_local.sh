#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate 2>/dev/null || true

./scripts/run_triage_pipeline.sh
python3 scripts/check_production_readiness.py --out reports/production_readiness.json
python3 scripts/build_quality_iteration_report.py \
  --scorecard reports/final_rare_scorecard.json \
  --kpi-policy config/kpi_policy.json \
  --out reports/quality_iteration_report.json
python3 scripts/enforce_kpi_gate.py \
  --scorecard reports/final_rare_scorecard.json \
  --policy config/kpi_policy.json \
  --out reports/kpi_gate.json
python3 scripts/validate_run_manifest.py --manifest config/run_manifest.local.json

echo "Canonical local run completed."
