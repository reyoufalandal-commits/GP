"""
Optional derived columns for CIC-style flow statistics (log1p, ratios).

Use only when training and scoring share the same pipeline; enable explicitly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def apply_cic_derived_features(df: pd.DataFrame, *, numeric_only: bool = True) -> pd.DataFrame:
    """
    Add non-destructive derived columns (prefixed ``der_``) for skewed magnitudes.

    Does not drop original columns.
    """
    out = df.copy()
    num = out.select_dtypes(include=[np.number])
    for c in num.columns:
        col = out[c]
        if (col >= 0).all() and col.max() > 100:
            out[f"der_log1p_{c}"] = np.log1p(col.clip(lower=0))
    if "Total Fwd Packets" in out.columns and "Total Backward Packets" in out.columns:
        tf = out["Total Fwd Packets"].astype(np.float64)
        tb = out["Total Backward Packets"].astype(np.float64)
        out["der_fwd_bwd_packet_ratio"] = tf / (tb + 1.0)
    return out
