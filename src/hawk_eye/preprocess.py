from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from hawk_eye.io import read_table, write_table


@dataclass(frozen=True)
class PreprocessConfig:
    label_column: str = "Label"
    id_columns: list[str] = None  # type: ignore[assignment]
    drop_exact_duplicates: bool = True
    drop_rows_with_missing_label: bool = True

    def __post_init__(self) -> None:
        if self.id_columns is None:
            object.__setattr__(self, "id_columns", [])


def infer_label_from_kaggle_filename(name: str) -> str:
    """
    For files like `Benign-Monday-no-metadata.parquet`, the label is the prefix before `-<weekday>-`.
    If a `Label` column already exists in the file, this is not used.
    """
    stem = Path(name).stem
    for suf in ("-no-metadata",):
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
    # stem e.g. Benign-Monday, WebAttacks-Thursday
    if "-" in stem:
        return stem.rsplit("-", 1)[0]
    return stem


def load_raw_tables(raw_dir: str | Path) -> pd.DataFrame:
    """
    Load and concatenate all CSV and Parquet files under raw_dir (recursive).
    Parquet files without a `Label` column get `Label` from the filename (Kaggle split files).
    """
    raw = Path(raw_dir)
    csvs = sorted(raw.rglob("*.csv"))
    parquets = sorted(raw.rglob("*.parquet"))
    if not csvs and not parquets:
        raise FileNotFoundError(f"No .csv or .parquet files found under {str(raw)}")

    frames: list[pd.DataFrame] = []
    for p in csvs:
        frames.append(pd.read_csv(p, low_memory=False))
    for p in parquets:
        df = read_table(p)
        if "Label" not in df.columns and "label" not in df.columns:
            df = df.copy()
            df["Label"] = infer_label_from_kaggle_filename(p.name)
        frames.append(df)

    return pd.concat(frames, ignore_index=True)


def load_raw_tables_capped(raw_dir: str | Path, max_rows_total: int, *, label_column: str) -> pd.DataFrame:
    """
    Load CSV/Parquet from raw_dir without reading entire huge files into memory at once:
    each file contributes at most ceil(max_rows_total / num_files) rows (head), then concat.
    """
    raw = Path(raw_dir)
    csvs = sorted(raw.rglob("*.csv"))
    parquets = sorted(raw.rglob("*.parquet"))
    files = csvs + parquets
    if not files:
        raise FileNotFoundError(f"No .csv or .parquet files found under {str(raw)}")
    n = len(files)
    per = max(1, (max_rows_total + n - 1) // n)

    frames: list[pd.DataFrame] = []
    for p in files:
        if p.suffix.lower() == ".csv":
            chunk = pd.read_csv(p, low_memory=False).head(per)
        else:
            chunk = read_table(p)
            if label_column not in chunk.columns:
                chunk = chunk.copy()
                chunk[label_column] = infer_label_from_kaggle_filename(p.name)
            chunk = chunk.head(per)
        frames.append(chunk)

    return pd.concat(frames, ignore_index=True)


def clean(df: pd.DataFrame, cfg: PreprocessConfig) -> pd.DataFrame:
    out = df.copy()

    if cfg.drop_rows_with_missing_label and cfg.label_column in out.columns:
        out = out.dropna(subset=[cfg.label_column])

    if cfg.drop_exact_duplicates:
        out = out.drop_duplicates()

    return out.reset_index(drop=True)


def build_manifest(
    *,
    raw_dir: str | Path,
    dataset_slug: str,
    rows: int,
    columns: list[str],
    split_seed: int,
    label_column: str,
) -> dict[str, Any]:
    return {
        "dataset_slug": dataset_slug,
        "raw_dir": str(Path(raw_dir).resolve()),
        "rows": rows,
        "columns": columns,
        "split_seed": split_seed,
        "label_column": label_column,
    }


def write_manifest(manifest: dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2, sort_keys=True))


def preprocess_to_interim(
    *,
    raw_dir: str | Path,
    out_path: str | Path,
    cfg: PreprocessConfig,
    max_rows_total: int | None = None,
) -> pd.DataFrame:
    if max_rows_total is not None:
        df = load_raw_tables_capped(raw_dir, max_rows_total, label_column=cfg.label_column)
    else:
        df = load_raw_tables(raw_dir)
    df = clean(df, cfg)
    write_table(df, out_path)
    return df

