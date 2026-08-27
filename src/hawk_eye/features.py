from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FeatureSpec:
    feature_columns: list[str]
    label_column: str
    id_columns: list[str]


def infer_feature_columns(df: pd.DataFrame, *, drop: Iterable[str]) -> list[str]:
    drop_set = set(drop)
    cols = [c for c in df.columns if c not in drop_set]
    return cols


def split_xy(df: pd.DataFrame, spec: FeatureSpec) -> tuple[pd.DataFrame, np.ndarray]:
    drop = set(spec.id_columns)
    drop.add(spec.label_column)

    if spec.label_column not in df.columns:
        hint = ""
        if spec.label_column == "label" and "Label" in df.columns:
            hint = " Pass --label-col Label (CICIDS / many Kaggle exports use capital Label)."
        elif spec.label_column == "Label" and "label" in df.columns:
            hint = " Pass --label-col label."
        raise KeyError(f"Missing label column: {spec.label_column}.{hint}")

    X = df.drop(columns=[c for c in drop if c in df.columns])
    y = df[spec.label_column].to_numpy()
    return X, y


def align_columns_strict(df: pd.DataFrame, expected_columns: list[str]) -> pd.DataFrame:
    """
    Return a frame with exactly `expected_columns`, in order.
    Extra columns (e.g. Label, IDs) are ignored; only missing required columns raise.
    """
    missing = [c for c in expected_columns if c not in df.columns]
    if missing:
        raise ValueError(
            "Input features do not match bundle feature contract. "
            f"Missing: {missing}. "
            "Use GET /api/v1/detections/supervised-feature-schema or Model lab “Insert one row (bundle features)”."
        )
    return df.loc[:, expected_columns].copy()

