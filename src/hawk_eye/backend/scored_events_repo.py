"""Batch inserts for optional scoring outputs into ``hawk_eye.db`` (``scored_events``)."""

from __future__ import annotations

import sqlite3
import time
from typing import Any

import pandas as pd


def insert_scored_results_df(
    conn: sqlite3.Connection,
    results: pd.DataFrame,
    *,
    tenant_id: int | None = None,
) -> int:
    """
    Insert scoring rows into ``scored_events``.

    Expects a ``score`` column; optional ``id``, ``timestamp``, ``label``, ``model_version``.
    Each row stores a JSON line of the full record in ``raw_json``.
    """
    cols = set(results.columns)
    has_id = "id" in cols
    has_ts = "timestamp" in cols
    if "score" not in cols:
        raise ValueError("Results must include a 'score' column.")

    n = len(results)
    if n == 0:
        return 0

    def get_col(name: str) -> pd.Series:
        if name in results.columns:
            return results[name]
        return pd.Series([None] * n)

    raw_json_lines = results.to_json(orient="records", lines=True).splitlines()
    if len(raw_json_lines) != n:
        raise ValueError("Internal error: raw_json line count mismatch")

    now = int(time.time())
    batch: list[tuple[Any, ...]] = []
    for i in range(n):
        row_id: str | None = None
        if has_id:
            v = get_col("id").iloc[i]
            row_id = str(v) if pd.notna(v) else None
        ts: str | None = None
        if has_ts:
            tv = get_col("timestamp").iloc[i]
            ts = str(tv) if pd.notna(tv) else None
        score = float(get_col("score").iloc[i])
        label: str | None = None
        if "label" in cols:
            lv = get_col("label").iloc[i]
            label = str(lv) if pd.notna(lv) else None
        model_version: str | None = None
        if "model_version" in cols:
            mv = get_col("model_version").iloc[i]
            model_version = str(mv) if pd.notna(mv) else None
        batch.append(
            (
                tenant_id,
                row_id,
                ts,
                score,
                label,
                model_version,
                raw_json_lines[i],
                now,
            )
        )

    conn.executemany(
        """
        INSERT INTO scored_events (
          tenant_id, row_id, timestamp, score, label, model_version, raw_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        batch,
    )
    return n
