from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def build_numeric_preprocessor(numeric_columns: list[str]) -> ColumnTransformer:
    """
    Median imputation + standard scaling for numeric IDS features.
    Shared by sklearn and PyTorch supervised training paths.
    """
    numeric = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    return ColumnTransformer(
        transformers=[("num", numeric, numeric_columns)],
        remainder="drop",
    )
