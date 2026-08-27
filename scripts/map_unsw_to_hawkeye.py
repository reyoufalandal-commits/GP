#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _enc_proto(s: pd.Series) -> np.ndarray:
    return s.astype(str).str.lower().map({"tcp": 6, "udp": 17, "icmp": 1}).fillna(0).to_numpy(dtype=float)


def main() -> int:
    ap = argparse.ArgumentParser(description="Map UNSW-NB15 rows to Hawk-Eye feature schema.")
    ap.add_argument("--input", required=True)
    ap.add_argument("--feature-columns", default="artifacts/hawk-eye-sup/feature_columns.json")
    ap.add_argument("--output", required=True)
    ap.add_argument("--out-label-col", default="Label")
    args = ap.parse_args()

    src = pd.read_csv(args.input)
    feat = json.loads(Path(args.feature_columns).read_text())
    out = pd.DataFrame(index=src.index)
    for c in feat:
        out[c] = 0.0

    # Core approximations from UNSW counters.
    if "Protocol" in out.columns and "proto" in src.columns:
        out["Protocol"] = _enc_proto(src["proto"])
    if "Flow Duration" in out.columns and "dur" in src.columns:
        out["Flow Duration"] = pd.to_numeric(src["dur"], errors="coerce").fillna(0.0) * 1_000_000.0
    if "Total Fwd Packets" in out.columns and "spkts" in src.columns:
        out["Total Fwd Packets"] = pd.to_numeric(src["spkts"], errors="coerce").fillna(0.0)
    if "Total Backward Packets" in out.columns and "dpkts" in src.columns:
        out["Total Backward Packets"] = pd.to_numeric(src["dpkts"], errors="coerce").fillna(0.0)
    if "Fwd Packets Length Total" in out.columns and "sbytes" in src.columns:
        out["Fwd Packets Length Total"] = pd.to_numeric(src["sbytes"], errors="coerce").fillna(0.0)
    if "Bwd Packets Length Total" in out.columns and "dbytes" in src.columns:
        out["Bwd Packets Length Total"] = pd.to_numeric(src["dbytes"], errors="coerce").fillna(0.0)
    if "Flow Packets/s" in out.columns and {"spkts", "dpkts", "dur"}.issubset(src.columns):
        dur = pd.to_numeric(src["dur"], errors="coerce").replace(0, np.nan)
        out["Flow Packets/s"] = (
            (pd.to_numeric(src["spkts"], errors="coerce").fillna(0.0) + pd.to_numeric(src["dpkts"], errors="coerce").fillna(0.0))
            / dur
        ).fillna(0.0)
    if "Flow Bytes/s" in out.columns and {"sbytes", "dbytes", "dur"}.issubset(src.columns):
        dur = pd.to_numeric(src["dur"], errors="coerce").replace(0, np.nan)
        out["Flow Bytes/s"] = (
            (pd.to_numeric(src["sbytes"], errors="coerce").fillna(0.0) + pd.to_numeric(src["dbytes"], errors="coerce").fillna(0.0))
            / dur
        ).fillna(0.0)
    if "Fwd Packet Length Mean" in out.columns and "smean" in src.columns:
        out["Fwd Packet Length Mean"] = pd.to_numeric(src["smean"], errors="coerce").fillna(0.0)
    if "Bwd Packet Length Mean" in out.columns and "dmean" in src.columns:
        out["Bwd Packet Length Mean"] = pd.to_numeric(src["dmean"], errors="coerce").fillna(0.0)
    if "Fwd IAT Mean" in out.columns and "sinpkt" in src.columns:
        out["Fwd IAT Mean"] = pd.to_numeric(src["sinpkt"], errors="coerce").fillna(0.0)
    if "Bwd IAT Mean" in out.columns and "dinpkt" in src.columns:
        out["Bwd IAT Mean"] = pd.to_numeric(src["dinpkt"], errors="coerce").fillna(0.0)

    if "label" in src.columns:
        is_benign = pd.to_numeric(src["label"], errors="coerce").fillna(0).astype(int) == 0
        attack_cat = src["attack_cat"].astype(str).fillna("UnknownAttack") if "attack_cat" in src.columns else pd.Series("Attack", index=src.index)
        out[args.out_label_col] = np.where(is_benign, "Benign", attack_cat)
    elif "attack_cat" in src.columns:
        out[args.out_label_col] = src["attack_cat"].astype(str).fillna("UnknownAttack")
    else:
        out[args.out_label_col] = "UnknownAttack"

    p = Path(args.output)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() == ".parquet":
        out.to_parquet(p, index=False)
    else:
        out.to_csv(p, index=False)
    print(json.dumps({"rows": len(out), "output": str(p.resolve()), "features": len(feat)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
