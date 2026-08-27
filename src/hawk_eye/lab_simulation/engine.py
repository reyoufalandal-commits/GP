"""Generate synthetic Zeek conn.log lines from scenarios or legacy preset names."""
from __future__ import annotations

import random
import signal
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from hawk_eye.lab_simulation.scenario import LabScenario, LabScenarioPhase, load_scenario_file, parse_scenario_dict

ZEEK_CONN_FIELDS_HEADER = (
    "#fields\tts\tuid\tproto\tduration\torig_bytes\tresp_bytes\torig_pkts\tresp_pkts\tid.orig_h\tid.resp_p\n"
)


def _line(
    ts: float,
    uid: str,
    proto: str,
    dur: str,
    ob: int,
    rb: int,
    op: int,
    rp: int,
    oip: str,
    rport: int,
) -> str:
    return f"{ts:.6f}\t{uid}\t{proto}\t{dur}\t{ob}\t{rb}\t{op}\t{rp}\t{oip}\t{rport}\n"


def _pick_port_rng(rng: random.Random, profile: str, line_index: int) -> int:
    if profile == "vertical_scan":
        return 1024 + (line_index % 200)
    if profile == "dns_like_udp":
        return 53
    pools = (443, 443, 80, 8080, 22)
    return pools[rng.randrange(len(pools))]


def _pick_orig_ip(rng: random.Random) -> str:
    k = rng.randint(0, 2)
    if k == 0:
        return f"10.{rng.randint(1, 200)}.{rng.randint(1, 250)}.{rng.randint(1, 250)}"
    if k == 1:
        return f"192.168.{rng.randint(1, 20)}.{rng.randint(1, 250)}"
    return f"172.16.{rng.randint(1, 20)}.{rng.randint(1, 250)}"


def _vary_bytes(rng: random.Random, base: int, spread: float = 0.25) -> int:
    lo = max(1, int(base * (1.0 - spread)))
    hi = max(lo + 1, int(base * (1.0 + spread)))
    return rng.randint(lo, hi)


def emit_row_for_profile(
    *,
    profile: str,
    line_index: int,
    ts: float,
    rng: random.Random,
) -> str:
    """One Zeek conn.log data line (no header) for the given profile."""
    uid = f"Sim{line_index:04x}{rng.randint(0, 15):x}"
    oip = _pick_orig_ip(rng)
    port = _pick_port_rng(rng, profile, line_index)

    if profile in ("benign", "benign_web", "steady_baseline"):
        ob, rb = _vary_bytes(rng, 900), _vary_bytes(rng, 1200)
        op, rp = rng.randint(4, 12), rng.randint(4, 14)
        dur_s = 0.8 + rng.random() * 2.5
        return _line(ts, uid, "tcp", f"{dur_s:.3f}", ob, rb, op, rp, oip, 443)

    if profile in ("heavy", "heavy_transfer"):
        ob, rb = _vary_bytes(rng, 400_000, 0.2), _vary_bytes(rng, 700_000, 0.2)
        op, rp = rng.randint(200, 500), rng.randint(200, 520)
        return _line(ts, uid, "tcp", f"{0.3 + rng.random() * 0.5:.3f}", ob, rb, op, rp, oip, 443)

    if profile in ("scan", "vertical_scan"):
        ob, rb = 60, 120
        return _line(ts, uid, "tcp", "0.001", ob, rb, 2, 2, oip, port)

    if profile == "horizontal_scan":
        # Many distinct origins toward one service port (lab narrative: wide sweep / many clients — synthetic only).
        oip = f"10.{(line_index // 64) % 5}.{line_index % 200}.{1 + (line_index * 7) % 240}"
        port = 80
        ob, rb = 80, 220
        return _line(ts, uid, "tcp", f"{0.02 + rng.random() * 0.08:.3f}", ob, rb, 3, 4, oip, port)

    if profile == "beacon_like":
        # Rhythmic similar-sized flows to HTTPS (lab narrative: periodic callback — not a real implant).
        ob = 160 + (line_index % 11) * 4
        rb = 200 + (line_index % 13) * 3
        dur = 1.8 + (line_index % 5) * 0.11
        return _line(ts, uid, "tcp", f"{dur:.3f}", ob, rb, 5, 6, oip, 443)

    if profile == "dns_like_udp":
        ob, rb = _vary_bytes(rng, 120), _vary_bytes(rng, 280)
        return _line(ts, uid, "udp", f"{0.05 + rng.random() * 0.4:.3f}", ob, rb, 2, 2, oip, 53)

    if profile == "mixed":
        r = line_index % 5
        if r == 0:
            return emit_row_for_profile(profile="benign_web", line_index=line_index, ts=ts, rng=rng)
        if r == 1:
            return emit_row_for_profile(profile="dns_like_udp", line_index=line_index, ts=ts, rng=rng)
        if r == 2:
            return emit_row_for_profile(profile="heavy_transfer", line_index=line_index, ts=ts, rng=rng)
        return _line(
            ts,
            uid,
            "tcp",
            f"{0.5 + rng.random():.3f}",
            _vary_bytes(rng, 500),
            _vary_bytes(rng, 500),
            4,
            4,
            oip,
            80,
        )

    if profile == "noisy_then_scan":
        # First 60% benign_web-like, rest scan-heavy
        cutoff = 6
        sub = line_index % 10
        if sub < cutoff:
            return emit_row_for_profile(profile="benign_web", line_index=line_index, ts=ts, rng=rng)
        return emit_row_for_profile(profile="vertical_scan", line_index=line_index, ts=ts, rng=rng)

    if profile == "mixed_attack_mix":
        cycle = (
            "benign_web",
            "dns_like_udp",
            "heavy_transfer",
            "vertical_scan",
            "horizontal_scan",
            "beacon_like",
            "mixed",
        )
        p = cycle[line_index % len(cycle)]
        return emit_row_for_profile(profile=p, line_index=line_index, ts=ts, rng=rng)

    raise ValueError(f"Unknown profile: {profile!r}")


def _timestamps_for_phase(phase: LabScenarioPhase, t0: float, rng: random.Random) -> list[float]:
    n = phase.total_lines
    out: list[float] = []
    dur = phase.duration_sec
    jitter = phase.jitter_sec
    step = phase.ts_step
    burst = phase.burst

    if dur is not None and dur > 0 and n > 0:
        for i in range(n):
            if n == 1:
                ts = t0 + dur / 2.0
            else:
                frac = i / (n - 1)
                ts = t0 + frac * dur + (rng.uniform(-jitter, jitter) if jitter else 0.0)
            out.append(ts)
        return out

    t = t0
    for i in range(n):
        t = t + step + (rng.uniform(-jitter, jitter) if jitter else 0.0)
        out.append(t)
        if burst and burst.every_n_lines > 0 and (i + 1) % burst.every_n_lines == 0:
            t += burst.gap_sec
    return out


def generate_lines_from_scenario(
    scenario: LabScenario,
    *,
    seed: int | None = None,
    start_ts: float | None = None,
) -> tuple[list[str], str]:
    """
    Returns (data_lines, scenario_label_for_artifacts).

    ``scenario_label_for_artifacts`` is a short string for lab config metadata.
    """
    rng = random.Random(seed)
    t0 = time.time() if start_ts is None else float(start_ts)
    lines: list[str] = []
    t_cursor = t0
    for ph in scenario.phases:
        ts_list = _timestamps_for_phase(ph, t_cursor, rng)
        if len(ts_list) != ph.total_lines:
            raise RuntimeError("internal: timestamp list length mismatch")
        for i in range(ph.total_lines):
            ts = ts_list[i]
            lines.append(
                emit_row_for_profile(
                    profile=ph.profile,
                    line_index=len(lines),
                    ts=ts,
                    rng=rng,
                )
            )
        t_cursor = ts_list[-1] + max(ph.ts_step, 0.001)
    label = "scenario:v1"
    if scenario.description:
        label = f"scenario:{scenario.description[:48]}"
    try:
        from hawk_eye.backend.prometheus_extra import LAB_SIMULATION_RUNS

        LAB_SIMULATION_RUNS.labels(mode="batch").inc()
    except Exception:
        pass
    return lines, label


def load_scenario(path: str | Path) -> LabScenario:
    """Load a scenario JSON file (see ``lab_scenarios/``)."""
    return load_scenario_file(path)


def generate_lines_legacy(scenario: str, n: int, start_ts: float, seed: int | None = None) -> list[str]:
    """Backward-compatible single-batch generation (original script behavior)."""
    rng = random.Random(seed)
    lines: list[str] = []
    t = float(start_ts)
    for i in range(max(1, n)):
        lines.append(
            emit_row_for_profile(profile=scenario, line_index=i, ts=t, rng=rng),
        )
        t += 0.01
    return lines


def iter_scenario_forever(
    scenario: LabScenario,
    *,
    seed: int | None,
    initial_ts: float | None,
) -> Iterator[tuple[list[str], str]]:
    """Yield (lines, label) for each full pass over the scenario; timestamps advance."""
    rng_master = random.Random(seed if seed is not None else int(time.time() * 1000) % (2**31))
    ts = time.time() if initial_ts is None else float(initial_ts)
    while True:
        sub_seed = rng_master.randrange(2**31)
        chunk, label = generate_lines_from_scenario(scenario, seed=sub_seed, start_ts=ts)
        if chunk:
            ts = float(chunk[-1].split("\t", 1)[0]) + 0.05
        yield chunk, label


def run_daemon(
    scenario: LabScenario,
    *,
    out_path: Path,
    seed: int | None,
    append: bool,
    pause_between_passes_sec: float = 0.25,
    write_config: Callable[[Path, str, int], dict[str, str]] | None = None,
    repo_root: Path | None = None,
) -> None:
    """
    Append scenario passes until SIGINT. Writes header once if file is new.
    """
    stop = False

    def _stop(*_a: Any) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    header_written = out_path.is_file() and out_path.stat().st_size > 0
    if not append and out_path.is_file():
        out_path.unlink()
        header_written = False

    cfg_written = False
    for chunk, label in iter_scenario_forever(scenario, seed=seed, initial_ts=time.time()):
        if stop:
            break
        if not chunk:
            time.sleep(pause_between_passes_sec)
            continue
        mode = "a" if header_written else "w"
        with out_path.open(mode, encoding="utf-8") as f:
            if not header_written:
                f.write(ZEEK_CONN_FIELDS_HEADER)
                header_written = True
            f.write("".join(chunk))
        try:
            from hawk_eye.backend.prometheus_extra import LAB_SIMULATION_RUNS

            LAB_SIMULATION_RUNS.labels(mode="daemon_pass").inc()
        except Exception:
            pass
        if write_config and repo_root and not cfg_written:
            write_config(out_path, label, len(chunk))
            cfg_written = True
        if stop:
            break
        time.sleep(pause_between_passes_sec)


def scenario_from_legacy(scenario_name: str, lines: int, seed: int | None) -> LabScenario:
    """Wrap legacy --scenario + --lines as a one-phase scenario."""
    return parse_scenario_dict(
        {
            "version": 1,
            "description": f"legacy:{scenario_name}",
            "phases": [{"profile": scenario_name, "total_lines": max(1, lines), "jitter_sec": 0.0}],
        }
    )
