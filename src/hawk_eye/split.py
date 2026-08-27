from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from hawk_eye.io import write_table


@dataclass(frozen=True)
class SplitConfig:
    seed: int = 42
    test_size: float = 0.2
    val_size: float = 0.2
    stratify: bool = True


def split_train_val_test(
    df: pd.DataFrame,
    *,
    label_column: str,
    cfg: SplitConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if label_column not in df.columns:
        raise KeyError(f"Missing label column: {label_column}")

    def _split(
        frame: pd.DataFrame, *, test_size: float, stratify: bool
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        y = frame[label_column] if stratify else None
        try:
            return train_test_split(
                frame, test_size=test_size, random_state=cfg.seed, stratify=y
            )
        except ValueError:
            # Rare classes (or tiny samples) break stratification — fall back once.
            return train_test_split(
                frame, test_size=test_size, random_state=cfg.seed, stratify=None
            )

    train_df, test_df = _split(df, test_size=cfg.test_size, stratify=cfg.stratify)

    # val fraction relative to remaining train portion
    val_rel = cfg.val_size / (1.0 - cfg.test_size)
    train_df, val_df = _split(train_df, test_size=val_rel, stratify=cfg.stratify)

    return train_df.reset_index(drop=True), val_df.reset_index(drop=True), test_df.reset_index(
        drop=True
    )


def write_splits(
    *,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    out_dir: str | Path,
    fmt: str = "parquet",
) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ext = "parquet" if fmt == "parquet" else "csv"
    write_table(train_df, out / f"train.{ext}")
    write_table(val_df, out / f"val.{ext}")
    write_table(test_df, out / f"test.{ext}")

