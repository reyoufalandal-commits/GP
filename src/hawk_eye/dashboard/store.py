from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from hawk_eye.backend.db import db_path, init_db
from hawk_eye.backend.scored_events_repo import insert_scored_results_df


def insert_results(
    results: pd.DataFrame,
    *,
    database: str | Path | None = None,
    tenant_id: int | None = None,
) -> int:
    """
    Insert scoring rows into the unified Hawk-Eye SQLite DB (``data/db/hawk_eye.db`` by default).

    ``database`` may point to another file for tests or one-off imports; production should use the default.
    """
    init_db()
    p = Path(database) if database is not None else db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as conn:
        conn.execute("PRAGMA foreign_keys=ON;")
        n = insert_scored_results_df(conn, results, tenant_id=tenant_id)
        conn.commit()
        return n
