from __future__ import annotations

from pathlib import Path

import pytest

from hawk_eye.lab_simulation.engine import (
    generate_lines_from_scenario,
    generate_lines_legacy,
    load_scenario,
    scenario_from_legacy,
)
from hawk_eye.lab_simulation.scenario import parse_scenario_dict
from hawk_eye.live.dual_mode import read_zeek_conn_log_with_fields


def test_parse_scenario_burst() -> None:
    s = parse_scenario_dict(
        {
            "version": 1,
            "phases": [
                {
                    "profile": "benign_web",
                    "total_lines": 3,
                    "burst": {"every_n_lines": 1, "gap_sec": 0.1},
                }
            ],
        }
    )
    assert s.phases[0].burst is not None
    assert s.phases[0].burst.every_n_lines == 1


def test_generate_lines_from_scenario_deterministic() -> None:
    scenario = parse_scenario_dict(
        {
            "version": 1,
            "description": "testmini",
            "phases": [{"profile": "mixed", "total_lines": 10, "jitter_sec": 0.0, "ts_step": 0.01}],
        }
    )
    a, _ = generate_lines_from_scenario(scenario, seed=123, start_ts=1000.0)
    b, _ = generate_lines_from_scenario(scenario, seed=123, start_ts=1000.0)
    assert len(a) == 10
    assert a == b


def test_legacy_matches_row_count() -> None:
    lines = generate_lines_legacy("benign", 25, start_ts=500.0, seed=0)
    assert len(lines) == 25
    assert "\t443\n" in lines[0] or lines[0].rstrip().endswith("443")


def test_preset_json_loads() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    p = repo_root / "lab_scenarios" / "lab_demo_quick.json"
    if not p.is_file():
        pytest.skip("lab_scenarios not present")
    sc = load_scenario(p)
    body, label = generate_lines_from_scenario(sc, seed=7, start_ts=2000.0)
    assert len(body) == 35
    assert "scenario:" in label or "lab_demo" in label


def test_scenario_round_trip_zeek_reader(tmp_path: Path) -> None:
    scenario = scenario_from_legacy("mixed", 12, seed=99)
    lines, _ = generate_lines_from_scenario(scenario, seed=99, start_ts=1.0)
    outp = tmp_path / "c.log"
    outp.write_text(
        "#fields\tts\tuid\tproto\tduration\torig_bytes\tresp_bytes\torig_pkts\tresp_pkts\tid.orig_h\tid.resp_p\n"
        + "".join(lines),
        encoding="utf-8",
    )
    df = read_zeek_conn_log_with_fields(outp)
    assert len(df) == 12
    assert "proto" in df.columns


def test_load_incident_prompt_mentions_risk_fields() -> None:
    from hawk_eye.llm_format import load_incident_report_prompt

    p = load_incident_report_prompt()
    assert "risk_headline" in p.lower() or "risk_level" in p.lower()
    assert "danger" in p.lower() or "tl;dr" in p.lower()
