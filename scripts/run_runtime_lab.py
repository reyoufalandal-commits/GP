#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from hawk_eye.decision_fusion import fuse_decisions
from hawk_eye.detect_novel import attack_uncertain_dataframe
from hawk_eye.io import read_table, write_table
from hawk_eye.open_set import score_open_set_dataframe
from hawk_eye.rag_triage import explain_dataframe


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_artifact_lock(lab: Path) -> dict[str, str]:
    p = lab / "config" / "artifact_lock.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def main() -> int:
    ap = argparse.ArgumentParser(description="Run isolated runtime-lab inference and reporting.")
    ap.add_argument("--lab-dir", required=True, help="Path to runtime lab directory.")
    ap.add_argument("--input", default=None, help="CSV/Parquet input path (defaults to lab input/test_flows.parquet).")
    ap.add_argument("--output-dir", default=None, help="Output directory (defaults to lab reports/<timestamp>).")
    args = ap.parse_args()

    lab = Path(args.lab_dir).expanduser().resolve()
    inp = Path(args.input).expanduser().resolve() if args.input else lab / "input" / "test_flows.parquet"
    out_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else lab / "reports" / _ts()
    out_dir.mkdir(parents=True, exist_ok=True)

    lock = _load_artifact_lock(lab)
    binary_dir = lab / lock.get("binary_dir", "artifacts/hawk-eye-binary")
    sup_dir = lab / lock.get("supervised_dir", "artifacts/hawk-eye-sup")
    anom_dir = lab / lock.get("anomaly_dir", "artifacts/hawk-eye-anomaly-ae-tuned")
    rag_index = lab / lock.get("rag_index", "artifacts/rag/rag_index.joblib")
    fusion_thr = lab / lock.get("thresholds_file", "config/thresholds_fusion_selected.json")

    for required in [binary_dir, sup_dir, anom_dir]:
        if not required.exists():
            raise FileNotFoundError(f"Missing required runtime artifact: {required}")

    df = read_table(inp)
    scored = attack_uncertain_dataframe(
        df,
        binary_dir=binary_dir,
        supervised_dir=sup_dir,
        anomaly_dir=anom_dir,
    )
    scored_path = out_dir / "attack_uncertain_scored.parquet"
    write_table(scored, scored_path)

    has_open_set = False
    try:
        os_df = score_open_set_dataframe(df, bundle_dir=sup_dir)
        has_open_set = True
        scored = pd.concat([scored.reset_index(drop=True), os_df.reset_index(drop=True)], axis=1)
    except Exception:
        pass

    if fusion_thr.exists():
        t = json.loads(fusion_thr.read_text())
        fused = fuse_decisions(
            scored,
            open_set_col="open_set_ood_score" if has_open_set else None,
            min_p_attack_known=float(t.get("min_p_attack_known", 0.7)),
            min_szd_uncertain=float(t.get("min_szd_uncertain", 70.0)),
            min_open_set_uncertain=float(t.get("min_open_set_uncertain", 0.6)),
        )
    else:
        fused = fuse_decisions(scored, open_set_col="open_set_ood_score" if has_open_set else None)

    fused_path = out_dir / "triage_decisions.parquet"
    write_table(fused, fused_path)

    rows_with_explanations = 0
    if rag_index.exists():
        explained = explain_dataframe(fused, index_path=rag_index, only_uncertain=True)
        explained_path = out_dir / "triage_with_explanations.parquet"
        write_table(explained, explained_path)
        rows_with_explanations = int((explained["llm_explanation_json"].astype(str).str.len() > 0).sum())

    summary = {
        "lab_dir": str(lab),
        "input": str(inp),
        "rows": int(len(df)),
        "has_open_set": bool(has_open_set),
        "decision_counts": fused["decision_label"].value_counts().to_dict(),
        "attack_uncertain": int((fused["decision_label"] == "AttackUncertain").sum()),
        "rows_with_explanations": rows_with_explanations,
        "output_dir": str(out_dir),
    }
    (out_dir / "run_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
