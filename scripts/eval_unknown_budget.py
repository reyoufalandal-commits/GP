#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from hawk_eye.io import read_table


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Evaluate unknown-like detection and choose thresholds under alert budget."
    )
    ap.add_argument("--input", required=True, help="CSV/Parquet with label + p_attack + szd/open-set columns.")
    ap.add_argument("--label-col", default="Label")
    ap.add_argument(
        "--known-label",
        action="append",
        default=[],
        help="Known family label value (repeatable). Rows not in this set are treated unknown-like.",
    )
    ap.add_argument("--p-attack-col", default="p_attack")
    ap.add_argument("--szd-col", default="suspected_zero_day_pct")
    ap.add_argument("--open-set-col", default="open_set_ood_score")
    ap.add_argument("--max-alert-rate", type=float, default=0.10)
    ap.add_argument("--out", default="reports/unknown_budget_eval.json")
    args = ap.parse_args()

    df = read_table(args.input)
    required = [args.label_col, args.p_attack_col, args.szd_col]
    for c in required:
        if c not in df.columns:
            raise SystemExit(f"Missing column: {c}")

    known = {str(x).strip() for x in args.known_label if str(x).strip()}
    if not known:
        raise SystemExit("Provide at least one --known-label.")
    y = df[args.label_col].astype(str).str.strip()
    is_unknown = ~y.isin(known)

    p_attack = df[args.p_attack_col].to_numpy(dtype=float)
    szd = df[args.szd_col].to_numpy(dtype=float)
    open_set = df[args.open_set_col].to_numpy(dtype=float) if args.open_set_col in df.columns else None

    best: dict[str, float] | None = None
    for p_t in np.linspace(0.05, 0.95, 19):
        for szd_t in np.linspace(50.0, 95.0, 10):
            # Candidate A: p_attack + szd only (works even without open-set)
            alert = (p_attack >= p_t) & (szd >= szd_t)
            alert_rate = float(alert.mean())
            if alert_rate <= args.max_alert_rate:
                rec = float((alert & is_unknown.to_numpy()).sum() / max(is_unknown.sum(), 1))
                if best is None or rec > best["unknown_recall"]:
                    best = {
                        "mode": "p_attack_and_szd",
                        "p_attack_threshold": float(p_t),
                        "szd_threshold": float(szd_t),
                        "open_set_threshold": None,
                        "unknown_recall": rec,
                        "alert_rate": alert_rate,
                    }

            # Candidate B: p_attack only fallback (some datasets won't separate with novelty/open-set)
            alert_p_only = p_attack >= p_t
            alert_rate_p_only = float(alert_p_only.mean())
            if alert_rate_p_only <= args.max_alert_rate:
                rec_p_only = float((alert_p_only & is_unknown.to_numpy()).sum() / max(is_unknown.sum(), 1))
                if best is None or rec_p_only > best["unknown_recall"]:
                    best = {
                        "mode": "p_attack_only",
                        "p_attack_threshold": float(p_t),
                        "szd_threshold": None,
                        "open_set_threshold": None,
                        "unknown_recall": rec_p_only,
                        "alert_rate": alert_rate_p_only,
                    }

            if open_set is not None:
                for o in np.linspace(0.40, 0.95, 12):
                    alert = (p_attack >= p_t) & ((szd >= szd_t) | (open_set >= o))
                    alert_rate = float(alert.mean())
                    if alert_rate > args.max_alert_rate:
                        continue
                    rec = float((alert & is_unknown.to_numpy()).sum() / max(is_unknown.sum(), 1))
                    if best is None or rec > best["unknown_recall"]:
                        best = {
                            "mode": "p_attack_and_szd_or_open_set",
                            "p_attack_threshold": float(p_t),
                            "szd_threshold": float(szd_t),
                            "open_set_threshold": float(o),
                            "unknown_recall": rec,
                            "alert_rate": alert_rate,
                        }

    if best is None:
        raise SystemExit("No threshold combination satisfies --max-alert-rate.")

    payload = {
        "rows": int(len(df)),
        "known_labels": sorted(known),
        "unknown_rows": int(is_unknown.sum()),
        "max_alert_rate": float(args.max_alert_rate),
        "recommendation": best,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
