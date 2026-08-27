# Hawk-Eye Model Governance

## Scope
This document defines operating assumptions and controls for local-first IDS use.

## Assumptions
- Input schema matches model feature contract.
- Threshold files are versioned and pinned per release.
- Unknown detection is probabilistic and triage-oriented, not CVE attribution.

## Policy Controls
- Threshold changes require approval and rollback plan (see `config/governance_policy.json`).
- KPI gate must pass before release (`config/kpi_policy.json` and `reports/kpi_gate.json`).
- Retraining cadence follows drift and time-based triggers.

## Release Gate
Required pass conditions:
- Macro F1 above policy minimum.
- Rare-class F1 floor satisfied.
- External unknown recall floor satisfied.
- Known alert rate under SOC budget.
- Test suite and runtime smoke checks green.

## Retuning Cadence
- Weekly: threshold review (alert budget, unknown recall).
- Monthly: retraining and calibration refresh.
- Incident-driven: immediate rollback/redeploy using pinned artifact lock.

