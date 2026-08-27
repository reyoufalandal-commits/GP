from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from hawk_eye.io import read_table, write_table

KNOWN_ATTACK = "KnownAttack"
ATTACK_UNCERTAIN = "AttackUncertain"
BENIGN_LOW_RISK = "BenignOrLowRisk"


def fuse_decisions(
    df: pd.DataFrame,
    *,
    binary_pred_col: str = "binary_prediction",
    p_attack_col: str = "p_attack",
    attack_uncertain_col: str = "is_attack_uncertain",
    novel_col: str = "is_novel_flagged",
    szd_pct_col: str = "suspected_zero_day_pct",
    open_set_col: str | None = "open_set_ood_score",
    min_p_attack_known: float = 0.70,
    min_szd_uncertain: float = 70.0,
    min_open_set_uncertain: float = 0.60,
) -> pd.DataFrame:
    """
    Unify binary + novelty + open-set into operational decision labels.

    Output columns:
    - ``decision_label`` in {KnownAttack, AttackUncertain, BenignOrLowRisk}
    - ``reason_codes`` as ``;``-joined machine-readable tags.
    """
    required = [binary_pred_col, p_attack_col, attack_uncertain_col, novel_col, szd_pct_col]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns for fusion: {missing}")
    if open_set_col and open_set_col not in df.columns:
        open_set_col = None

    labels: list[str] = []
    reasons: list[str] = []
    tiers: list[str] = []

    for _, row in df.iterrows():
        binary_pred = str(row[binary_pred_col]).strip()
        p_attack = float(row[p_attack_col])
        is_unc = bool(row[attack_uncertain_col])
        is_novel = bool(row[novel_col])
        szd = float(row[szd_pct_col])
        open_set = float(row[open_set_col]) if open_set_col else None

        rs: list[str] = []
        if binary_pred.lower() == "attack":
            if p_attack >= min_p_attack_known:
                rs.append("binary_attack_high_conf")
            else:
                rs.append("binary_attack_low_conf")
            if is_unc:
                rs.append("attack_uncertain_signal")
            if is_novel:
                rs.append("novel_flag")
            if szd >= min_szd_uncertain:
                rs.append("high_szd_pct")
            if open_set is not None and open_set >= min_open_set_uncertain:
                rs.append("high_open_set_ood")

            uncertain = (
                is_unc
                or is_novel
                or szd >= min_szd_uncertain
                or (open_set is not None and open_set >= min_open_set_uncertain)
                or p_attack < min_p_attack_known
            )
            if uncertain:
                labels.append(ATTACK_UNCERTAIN)
                tiers.append("high" if p_attack >= min_p_attack_known else "medium")
            else:
                labels.append(KNOWN_ATTACK)
                tiers.append("high")
        else:
            if open_set is not None and open_set >= min_open_set_uncertain:
                labels.append(ATTACK_UNCERTAIN)
                rs.append("benign_pred_high_open_set_ood")
                tiers.append("medium")
            elif is_novel or szd >= min_szd_uncertain:
                labels.append(ATTACK_UNCERTAIN)
                rs.append("benign_pred_novelty_signal")
                tiers.append("medium")
            else:
                labels.append(BENIGN_LOW_RISK)
                rs.append("benign_binary_pred")
                tiers.append("low")
        reasons.append(";".join(rs))

    out = df.copy()
    out["decision_label"] = labels
    out["decision_risk_tier"] = tiers
    out["reason_codes"] = reasons
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Fuse binary+novelty+open-set into one decision label.")
    ap.add_argument("--input", required=True, help="Input scored CSV/Parquet.")
    ap.add_argument("--output", required=True, help="Output CSV/Parquet with decision columns.")
    ap.add_argument("--open-set-col", default="open_set_ood_score")
    ap.add_argument("--min-p-attack-known", type=float, default=0.70)
    ap.add_argument("--min-szd-uncertain", type=float, default=70.0)
    ap.add_argument("--min-open-set-uncertain", type=float, default=0.60)
    ap.add_argument(
        "--thresholds-file",
        default=None,
        help="Optional JSON overrides for min_p_attack_known/min_szd_uncertain/min_open_set_uncertain.",
    )
    ap.add_argument("--emit-run-summary", default=None)
    args = ap.parse_args()

    min_p_attack_known = float(args.min_p_attack_known)
    min_szd_uncertain = float(args.min_szd_uncertain)
    min_open_set_uncertain = float(args.min_open_set_uncertain)
    if args.thresholds_file:
        data = json.loads(Path(args.thresholds_file).read_text())
        if "min_p_attack_known" in data:
            min_p_attack_known = float(data["min_p_attack_known"])
        if "min_szd_uncertain" in data:
            min_szd_uncertain = float(data["min_szd_uncertain"])
        if "min_open_set_uncertain" in data:
            min_open_set_uncertain = float(data["min_open_set_uncertain"])

    df = read_table(args.input)
    out = fuse_decisions(
        df,
        open_set_col=args.open_set_col if args.open_set_col else None,
        min_p_attack_known=min_p_attack_known,
        min_szd_uncertain=min_szd_uncertain,
        min_open_set_uncertain=min_open_set_uncertain,
    )
    write_table(out, args.output)

    summary: dict[str, Any] = {
        "rows": len(out),
        "output": str(Path(args.output).resolve()),
        "decision_counts": out["decision_label"].value_counts().to_dict(),
    }
    if args.emit_run_summary:
        Path(args.emit_run_summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.emit_run_summary).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
