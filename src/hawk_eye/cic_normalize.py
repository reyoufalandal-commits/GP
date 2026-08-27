from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


def _variant_keys(name: str) -> set[str]:
    n = name.strip()
    keys = {
        n.lower(),
        n.lower().replace(" ", "_"),
        n.lower().replace(" ", ""),
        re.sub(r"\s+", " ", n.lower()),
    }
    return {k for k in keys if k}


def build_alias_to_canonical(
    feature_columns: list[str],
    extra_aliases: dict[str, str] | None = None,
) -> dict[str, str]:
    """Map common header variants (case, underscores) to bundle column names."""
    rev: dict[str, str] = {}
    for col in feature_columns:
        for k in _variant_keys(col):
            rev[k] = col
    if extra_aliases:
        for raw, canonical in extra_aliases.items():
            rev[raw.strip().lower()] = canonical
    return rev


def load_extra_aliases(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    data: Any = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("Alias file must be a JSON object mapping alternate_name -> canonical_name")
    out: dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out


# Typical ID / metadata columns from CICFlowMeter or PCAP tools (not model features)
_DROP_SUBSTR = (
    "flow id",
    "flow_id",
    "timestamp",
    "src ip",
    "dst ip",
    "source ip",
    "destination ip",
    "ip src",
    "ip dst",
)


def normalize_flow_dataframe(
    df: pd.DataFrame,
    *,
    feature_columns: list[str],
    label_column: str | None = None,
    extra_aliases: dict[str, str] | None = None,
) -> pd.DataFrame:
    """
    Rename columns to match bundle feature names; drop obvious non-feature ID columns.
    """
    alias_map = build_alias_to_canonical(feature_columns, extra_aliases)
    rename: dict[str, str] = {}
    for c in df.columns:
        if label_column and c == label_column:
            continue
        key = c.strip().lower()
        key_us = key.replace(" ", "_")
        if key in alias_map:
            rename[c] = alias_map[key]
        elif key_us in alias_map:
            rename[c] = alias_map[key_us]
        elif c in alias_map:
            rename[c] = alias_map[c]

    out = df.rename(columns=rename)
    drop_cols: list[str] = []
    for c in out.columns:
        if label_column and c == label_column:
            continue
        cl = c.lower()
        if any(s in cl for s in _DROP_SUBSTR):
            drop_cols.append(c)
    out = out.drop(columns=[c for c in drop_cols if c in out.columns], errors="ignore")
    return out


def dataframe_matches_features(
    df: pd.DataFrame,
    feature_columns: list[str],
    *,
    label_column: str | None = None,
) -> tuple[list[str], list[str]]:
    """Return (missing, extra_nonlabel) compared to expected feature columns."""
    have = set(df.columns)
    if label_column:
        have.discard(label_column)
    missing = [c for c in feature_columns if c not in df.columns]
    extra = [c for c in have if c not in set(feature_columns)]
    return missing, extra
