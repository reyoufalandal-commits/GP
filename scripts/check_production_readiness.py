#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _exists(path: str) -> bool:
    return Path(path).exists()


def main() -> int:
    ap = argparse.ArgumentParser(description="Exit checklist gate for Hawk-Eye production rollout.")
    ap.add_argument("--out", default="reports/production_readiness.json")
    args = ap.parse_args()

    checks = {
        "baseline_metrics_present": _exists("reports/baseline/latest.json"),
        "run_manifest_present": _exists("config/run_manifest.local.json"),
        "run_manifest_validated": _exists("reports/run_manifest_validated.json"),
        "triage_pipeline_script_present": _exists("scripts/run_triage_pipeline.sh"),
        "canonical_local_script_present": _exists("scripts/run_canonical_local.sh"),
        "kpi_policy_present": _exists("config/kpi_policy.json"),
        "kpi_gate_report_present": _exists("reports/kpi_gate.json"),
        "rag_seed_corpus_present": _exists("data/knowledge/rag_corpus_seed.jsonl"),
        "api_service_present": _exists("src/hawk_eye/api_service.py"),
        "governance_policy_present": _exists("config/governance_policy.json"),
        "ops_guardrails_present": _exists("src/hawk_eye/ops_guardrails.py"),
    }
    payload = {
        "checks": checks,
        "passed": all(checks.values()),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0 if payload["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
