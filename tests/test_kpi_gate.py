from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_kpi_gate_passes_when_values_above_thresholds() -> None:
    scorecard = {
        "train_compare": {"boost_macro_f1": 0.8},
        "baseline": {"lowest_f1_classes_top10": [{"class": "PortScan", "f1": 0.82}]},
        "unsw_unknown_eval": {"adaptive_unknown_recall_attack_uncertain": 0.22},
        "unsw_novelty_calibrator_eval": {
            "calibrator_unknown_recall": 0.14,
            "calibrator_known_alert_rate": 0.03,
            "calibrator_alert_rate": 0.09,
        },
    }
    policy = {
        "macro_f1_min": 0.75,
        "rare_class_f1_min": 0.8,
        "rare_classes": ["PortScan"],
        "unknown_recall_external_min": 0.14,
        "known_alert_rate_max": 0.08,
        "max_alert_rate_external": 0.12,
    }
    root = Path(__file__).resolve().parents[1]
    score = root / "reports" / "tmp_test_kpi_scorecard.json"
    pol = root / "reports" / "tmp_test_kpi_policy.json"
    outp = root / "reports" / "tmp_test_kpi_out.json"
    score.write_text(json.dumps(scorecard))
    pol.write_text(json.dumps(policy))
    cmd = [
        sys.executable,
        "scripts/enforce_kpi_gate.py",
        "--scorecard",
        str(score),
        "--policy",
        str(pol),
        "--out",
        str(outp),
    ]
    p = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert p.returncode == 0
    out = json.loads(outp.read_text())
    assert out["passed"] is True

