"""JSON scenario format for lab conn.log simulation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BurstConfig:
    """Optional burst / idle pattern within a phase."""

    every_n_lines: int
    gap_sec: float


@dataclass(frozen=True)
class LabScenarioPhase:
    profile: str
    total_lines: int
    duration_sec: float | None
    jitter_sec: float
    ts_step: float
    burst: BurstConfig | None


@dataclass(frozen=True)
class LabScenario:
    version: int
    phases: list[LabScenarioPhase]
    description: str | None


def _phase_line_count(raw: dict[str, Any]) -> int:
    if "total_lines" in raw:
        return max(1, int(raw["total_lines"]))
    d = raw.get("duration_sec")
    rps = raw.get("rows_per_sec")
    if d is not None and rps is not None:
        return max(1, int(float(d) * float(rps)))
    raise ValueError(
        "Each phase needs total_lines or (duration_sec and rows_per_sec). "
        f"Got keys: {list(raw.keys())}"
    )


def _parse_burst(raw: Any) -> BurstConfig | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise TypeError("burst must be an object or omitted")
    every = int(raw.get("every_n_lines", raw.get("every", 0)))
    gap = float(raw.get("gap_sec", raw.get("pause_sec", 0.0)))
    if every <= 0 or gap <= 0:
        raise ValueError("burst requires positive every_n_lines and gap_sec")
    return BurstConfig(every_n_lines=every, gap_sec=gap)


def parse_scenario_dict(data: dict[str, Any]) -> LabScenario:
    ver = int(data.get("version", 1))
    phases_in = data.get("phases")
    if not isinstance(phases_in, list) or not phases_in:
        raise ValueError("scenario must include a non-empty 'phases' array")
    phases: list[LabScenarioPhase] = []
    for i, raw in enumerate(phases_in):
        if not isinstance(raw, dict):
            raise TypeError(f"phases[{i}] must be an object")
        profile = str(raw.get("profile", "")).strip()
        if not profile:
            raise ValueError(f"phases[{i}].profile is required")
        tl = _phase_line_count(raw)
        dur = raw.get("duration_sec")
        duration_sec = float(dur) if dur is not None else None
        jitter_sec = float(raw.get("jitter_sec", 0.0) or 0.0)
        ts_step = float(raw.get("ts_step", 0.01) or 0.01)
        burst = _parse_burst(raw.get("burst"))
        phases.append(
            LabScenarioPhase(
                profile=profile,
                total_lines=tl,
                duration_sec=duration_sec,
                jitter_sec=jitter_sec,
                ts_step=ts_step,
                burst=burst,
            )
        )
    desc = data.get("description")
    return LabScenario(version=ver, phases=phases, description=str(desc) if desc else None)


def load_scenario_file(path: str | Path) -> LabScenario:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("scenario file must contain a JSON object")
    return parse_scenario_dict(data)
