from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from hawk_eye.io import read_table, write_table


DEFAULT_BENIGN = {"BENIGN", "Benign", "benign"}


def export_benign_splits(
    *,
    processed_dir: str | Path,
    label_col: str = "Label",
    benign_values: set[str] | None = None,
    out_dir: str | Path | None = None,
) -> None:
    processed = Path(processed_dir)
    out = Path(out_dir or processed)
    out.mkdir(parents=True, exist_ok=True)
    benign = benign_values or DEFAULT_BENIGN

    for split in ("train", "val", "test"):
        path = processed / f"{split}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}")
        df = read_table(path)
        if label_col not in df.columns:
            raise KeyError(f"Missing {label_col} in {path}")
        mask = df[label_col].astype(str).isin(benign)
        sub = df.loc[mask].reset_index(drop=True)
        write_table(sub, out / f"benign_{split}.csv")
        print(f"{split}: {len(sub)} benign rows (of {len(df)}) -> {out / f'benign_{split}.csv'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Export benign-only rows from data/processed splits.")
    ap.add_argument("--processed-dir", default="data/processed", help="Directory with train/val/test.csv")
    ap.add_argument("--label-col", default="Label")
    ap.add_argument(
        "--benign-values",
        default="BENIGN,Benign,benign",
        help="Comma-separated label values treated as benign.",
    )
    ap.add_argument("--out-dir", default=None, help="Output directory (default: same as processed-dir)")
    args = ap.parse_args()
    benign_set = {x.strip() for x in args.benign_values.split(",") if x.strip()}
    export_benign_splits(
        processed_dir=args.processed_dir,
        label_col=args.label_col,
        benign_values=benign_set,
        out_dir=args.out_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
