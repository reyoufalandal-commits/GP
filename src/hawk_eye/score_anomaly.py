from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from hawk_eye.anomaly_bundle import load_anomaly_bundle
from hawk_eye.anomaly_score import score_frame_anomaly
from hawk_eye.io import read_table, write_table
from hawk_eye.paths import resolve_anomaly_dir


def score_anomaly_dataframe(df: pd.DataFrame, *, bundle_dir: str | Path | None = None) -> pd.DataFrame:
    bdir = resolve_anomaly_dir(bundle_dir=bundle_dir)
    bundle = load_anomaly_bundle(bdir)
    scores = score_frame_anomaly(df, bundle)
    thr = float(bundle.config["threshold"])
    out = pd.DataFrame(
        {
            "anomaly_score": scores,
            "threshold": thr,
            "is_anomaly": scores > thr,
        }
    )
    out["model_type"] = bundle.config.get("model_type", "")
    out["bundle_version"] = bundle.config.get("bundle_version", "")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="CSV/Parquet with same feature columns as training.")
    ap.add_argument("--output", required=True)
    ap.add_argument("--model-dir", default=None, help="Override anomaly bundle dir.")
    ap.add_argument("--jsonl", action="store_true", help="Also write results.jsonl next to output.")
    args = ap.parse_args()

    df = read_table(args.input)
    out = score_anomaly_dataframe(df, bundle_dir=args.model_dir)
    write_table(out, args.output)

    if args.jsonl:
        jsonl_path = Path(args.output).with_suffix("").with_name("anomaly_results.jsonl")
        with jsonl_path.open("w") as f:
            for i in range(len(out)):
                f.write(json.dumps(out.iloc[i].to_dict()) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
