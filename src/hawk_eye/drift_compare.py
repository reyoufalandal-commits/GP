"""Numeric column drift comparison (shared by CLI and optional governance reports)."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from hawk_eye.io import read_table


def read_limited(path: str | Path, max_rows: int) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p, nrows=max_rows)
    df = read_table(p)
    return df.head(max_rows)


def compare_numeric_drift(
    reference: str | Path,
    sample: str | Path,
    *,
    columns: list[str] | None = None,
    max_rows_ref: int = 50_000,
    max_rows_sample: int = 50_000,
) -> list[dict[str, Any]]:
    ref = read_limited(reference, max_rows_ref)
    smp = read_limited(sample, max_rows_sample)

    if columns is not None:
        cols = [c for c in columns if c in ref.columns and c in smp.columns]
    else:
        ref_num = ref.select_dtypes(include=[np.number]).columns
        smp_num = smp.select_dtypes(include=[np.number]).columns
        cols = [c for c in ref_num if c in smp_num]

    rows: list[dict[str, Any]] = []
    for c in cols:
        r = ref[c].astype(float)
        s = smp[c].astype(float)
        rm, rs = float(r.mean()), float(r.std(ddof=0))
        sm, ss = float(s.mean()), float(s.std(ddof=0))
        denom = abs(rm) if abs(rm) > 1e-12 else 1.0
        rel = abs(sm - rm) / denom
        rows.append(
            {
                "column": c,
                "ref_mean": rm,
                "ref_std": rs,
                "sample_mean": sm,
                "sample_std": ss,
                "abs_mean_shift_ratio": rel,
            }
        )

    rows.sort(key=lambda x: x["abs_mean_shift_ratio"], reverse=True)
    return rows


def build_drift_report_payload(
    *,
    reference: str | Path,
    sample: str | Path,
    columns: list[str] | None = None,
    max_rows_ref: int = 50_000,
    max_rows_sample: int = 50_000,
) -> dict[str, Any]:
    rows = compare_numeric_drift(
        reference,
        sample,
        columns=columns,
        max_rows_ref=max_rows_ref,
        max_rows_sample=max_rows_sample,
    )
    top = rows[:20]
    return {
        "generated_at_unix": int(time.time()),
        "reference": str(Path(reference).resolve()),
        "sample": str(Path(sample).resolve()),
        "column_count": len(rows),
        "top_by_mean_shift": top,
        "all_columns": rows,
    }
