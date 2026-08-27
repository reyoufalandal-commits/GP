#!/usr/bin/env python3
"""
Append synthetic Zeek conn.log lines for **authorized lab / classroom** testing.

Does not generate real attacks — only tab-separated rows that Zeek would parse, with
different volume/duration patterns so ML scoring may label them differently once bundles exist.

Usage (legacy preset):
  python3 scripts/lab_simulate_conn_log.py --out data/lab/sim_conn.log --scenario mixed --lines 40

Usage (JSON scenario — see lab_scenarios/ and docs/LAB_SYNTHETIC_PROFILES.md):
  python3 scripts/lab_simulate_conn_log.py --scenario-file lab_scenarios/steady_baseline.json --out data/lab/sim_conn.log
  python3 scripts/lab_simulate_conn_log.py --scenario-file lab_scenarios/classroom_full_menu.json --out data/lab/sim_conn.log
  python3 scripts/lab_simulate_conn_log.py --scenario-file lab_scenarios/noisy_then_scan.json --daemon --out data/lab/sim_conn.log

By default this also writes ``data/lab/stream_lab.generated.json`` and ``hawk_eye_stream_env.sh``
(plus ``config/generated_stream_lab.json``) so you can ``source`` the shell snippet or run
``python3 scripts/apply_lab_stream_config.py`` to persist paths into SQLite.

Only use on networks and systems you own or are allowed to test.
Synthetic data only; do not point tools at networks you are not authorized to test.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from hawk_eye.lab_simulation import (  # noqa: E402
    ZEEK_CONN_FIELDS_HEADER,
    generate_lines_from_scenario,
    generate_lines_legacy,
    load_scenario,
    run_daemon,
    scenario_from_legacy,
)
from hawk_eye.lab_stream_config import write_stream_lab_artifacts  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Write synthetic Zeek conn.log lines for lab testing.",
        epilog="See lab_scenarios/*.json for scenario-file format (phases, profiles, jitter, burst).",
    )
    ap.add_argument("--out", default="data/lab/sim_conn.log", help="Output path (created if needed).")
    ap.add_argument(
        "--scenario",
        choices=("benign", "heavy", "scan", "mixed"),
        default="mixed",
        help="Legacy preset (use with --lines). Ignored when --scenario-file is set.",
    )
    ap.add_argument(
        "--scenario-file",
        type=Path,
        default=None,
        help="JSON scenario (phased profiles). See lab_scenarios/ for examples.",
    )
    ap.add_argument("--lines", type=int, default=30, help="Legacy mode: number of data rows.")
    ap.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible classroom runs.")
    ap.add_argument("--append", action="store_true", help="Append instead of overwrite (header only if new file).")
    ap.add_argument(
        "--daemon",
        action="store_true",
        help="Loop scenario passes until Ctrl+C (for use while a Live stream is running).",
    )
    ap.add_argument(
        "--no-config",
        action="store_true",
        help="Do not write stream_lab.generated.json / hawk_eye_stream_env.sh / config mirror.",
    )
    args = ap.parse_args()
    p = Path(args.out)
    p.parent.mkdir(parents=True, exist_ok=True)

    if args.scenario_file:
        scenario = load_scenario(args.scenario_file)
        scen_label = args.scenario_file.stem
    else:
        scenario = scenario_from_legacy(args.scenario, max(1, args.lines), args.seed)
        scen_label = args.scenario

    if args.daemon:
        if args.append:
            print("Daemon mode: appending passes to", p.resolve(), "(Ctrl+C to stop)", flush=True)
        else:
            print("Daemon mode: writing to", p.resolve(), "(Ctrl+C to stop)", flush=True)

        def _cfg(out: Path, label: str, line_count: int) -> dict[str, str]:
            return write_stream_lab_artifacts(
                conn_log_path=out,
                scenario=f"{scen_label}:{label}",
                line_count=line_count,
                repo_root=ROOT,
            )

        run_daemon(
            scenario,
            out_path=p,
            seed=args.seed,
            append=args.append,
            write_config=None if args.no_config else _cfg,
            repo_root=ROOT,
        )
        return 0

    if args.scenario_file:
        body, label = generate_lines_from_scenario(scenario, seed=args.seed, start_ts=time.time())
        meta = f"{scen_label}:{label}"
    else:
        body = generate_lines_legacy(args.scenario, max(1, args.lines), time.time(), seed=args.seed)
        meta = args.scenario

    text_body = "".join(body)
    if args.append and p.exists():
        p.write_text(p.read_text(encoding="utf-8", errors="ignore") + text_body, encoding="utf-8")
    else:
        p.write_text(ZEEK_CONN_FIELDS_HEADER + text_body, encoding="utf-8")
    print(f"Wrote {len(body)} rows to {p.resolve()}")
    if not args.no_config:
        paths = write_stream_lab_artifacts(
            conn_log_path=p,
            scenario=meta,
            line_count=len(body),
            repo_root=ROOT,
        )
        print("Generated config artifacts:")
        for k, v in paths.items():
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
