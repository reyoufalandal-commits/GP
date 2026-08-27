from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_table(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() in {".parquet"}:
        try:
            return pd.read_parquet(p)
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Failed to read Parquet. Install a Parquet engine (recommended: pyarrow). "
                f"Original error: {e}"
            ) from e
    if p.suffix.lower() in {".csv"}:
        return pd.read_csv(p)
    raise ValueError(f"Unsupported file type: {p.suffix}. Use .csv or .parquet.")


def write_table(df: pd.DataFrame, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() in {".parquet"}:
        try:
            df.to_parquet(p, index=False)
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Failed to write Parquet. Install a Parquet engine (recommended: pyarrow). "
                f"Original error: {e}"
            ) from e
        return
    if p.suffix.lower() in {".csv"}:
        df.to_csv(p, index=False)
        return
    raise ValueError(f"Unsupported file type: {p.suffix}. Use .csv or .parquet.")

