"""Scenario-driven synthetic Zeek conn.log generation for authorized lab use."""

from __future__ import annotations

from hawk_eye.lab_simulation.engine import (
    ZEEK_CONN_FIELDS_HEADER,
    generate_lines_from_scenario,
    generate_lines_legacy,
    load_scenario,
    run_daemon,
    scenario_from_legacy,
)
from hawk_eye.lab_simulation.scenario import LabScenario, LabScenarioPhase

__all__ = [
    "ZEEK_CONN_FIELDS_HEADER",
    "LabScenario",
    "LabScenarioPhase",
    "load_scenario",
    "generate_lines_from_scenario",
    "generate_lines_legacy",
    "run_daemon",
    "scenario_from_legacy",
]
