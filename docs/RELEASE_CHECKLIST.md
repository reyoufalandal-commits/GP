# Hawk-Eye Release Checklist (Local)

## Artifacts
- [ ] `artifacts/hawk-eye-binary` exists
- [ ] `artifacts/hawk-eye-sup` exists
- [ ] `artifacts/hawk-eye-anomaly-ae-tuned` exists
- [ ] `reports/thresholds_fusion_selected.json` exists

## Reports
- [ ] `reports/final_rare_scorecard.json`
- [ ] `reports/quality_iteration_report.json`
- [ ] `reports/kpi_gate.json`
- [ ] `reports/production_readiness.json`

## Tests
- [ ] `pytest -q` passes
- [ ] Runtime lab smoke run succeeds
- [ ] API `/health` and `/ready` respond correctly

## Operations
- [ ] `config/run_manifest.local.json` validated
- [ ] `config/kpi_policy.json` reviewed
- [ ] `config/governance_policy.json` reviewed
- [ ] Operator guide current (`docs/OPERATOR_GUIDE_LOCAL.md`)

