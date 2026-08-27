"""Indexed paths for stream jobs (Parquet, summary JSON, state, progress)."""

from __future__ import annotations

import sqlite3
import time


def upsert_stream_job_artifact_index(
    conn: sqlite3.Connection,
    *,
    job_id: int,
    parquet_path: str | None,
    summary_json_path: str | None,
    state_json_path: str | None,
    progress_json_path: str | None = None,
) -> None:
    """Store or replace artifact paths for a completed ``stream_collect`` job."""
    now = int(time.time())
    conn.execute(
        """
        INSERT INTO stream_job_artifact_index (
          job_id, parquet_path, summary_json_path, state_json_path, progress_json_path, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
          parquet_path = excluded.parquet_path,
          summary_json_path = excluded.summary_json_path,
          state_json_path = excluded.state_json_path,
          progress_json_path = excluded.progress_json_path,
          updated_at = excluded.updated_at
        """,
        (job_id, parquet_path, summary_json_path, state_json_path, progress_json_path, now),
    )
