"""Prometheus metrics not tied to a single route (import for registration side effects)."""

from __future__ import annotations

from prometheus_client import Counter

LAB_SIMULATION_RUNS = Counter(
    "hawk_eye_lab_simulation_runs_total",
    "Synthetic Zeek conn.log lab simulation completed (batch or daemon pass)",
    ["mode"],
)
