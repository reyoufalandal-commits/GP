from __future__ import annotations

import sqlite3
import time

import pandas as pd
import pytest

from hawk_eye.backend.db import init_db
from hawk_eye.backend.job_artifacts_repo import upsert_stream_job_artifact_index
from hawk_eye.backend.scored_events_repo import insert_scored_results_df
from hawk_eye.dashboard.store import insert_results


def _patch_db_path(monkeypatch: pytest.MonkeyPatch, dbf) -> None:
    """Patch db_path in both defining module and re-exporting consumers."""
    monkeypatch.setattr("hawk_eye.backend.db.db_path", lambda: dbf)
    monkeypatch.setattr("hawk_eye.dashboard.store.db_path", lambda: dbf)


def test_insert_results_uses_unified_hawk_eye_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    dbf = tmp_path / "hawk_eye.db"
    _patch_db_path(monkeypatch, dbf)
    init_db()
    df = pd.DataFrame({"score": [0.5, 0.2], "label": ["a", "b"]})
    assert insert_results(df) == 2
    con = sqlite3.connect(dbf)
    n = con.execute("SELECT COUNT(*) FROM scored_events").fetchone()[0]
    assert n == 2
    rows = con.execute("SELECT score, label, tenant_id FROM scored_events ORDER BY id").fetchall()
    assert rows[0][0] == pytest.approx(0.5)
    assert rows[0][1] == "a"
    assert rows[0][2] is None
    con.close()


def test_insert_results_tenant_id(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    dbf = tmp_path / "hawk_eye.db"
    _patch_db_path(monkeypatch, dbf)
    init_db()
    with sqlite3.connect(dbf) as c:
        c.execute("INSERT INTO tenants(name, created_at) VALUES (?, ?)", ("t1", int(time.time())))
        tid = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
        c.commit()
    df = pd.DataFrame({"score": [1.0]})
    assert insert_results(df, tenant_id=tid) == 1
    con = sqlite3.connect(dbf)
    t = con.execute("SELECT tenant_id FROM scored_events").fetchone()[0]
    assert t == tid
    con.close()


def test_insert_scored_results_df_requires_score() -> None:
    con = sqlite3.connect(":memory:")
    con.execute(
        """
        CREATE TABLE scored_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tenant_id INTEGER,
          row_id TEXT,
          timestamp TEXT,
          score REAL NOT NULL,
          label TEXT,
          model_version TEXT,
          raw_json TEXT NOT NULL,
          created_at INTEGER NOT NULL
        );
        """
    )
    df = pd.DataFrame({"label": ["x"]})
    with pytest.raises(ValueError, match="score"):
        insert_scored_results_df(con, df)


def test_stream_job_artifact_index_upsert(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    dbf = tmp_path / "hawk_eye.db"
    _patch_db_path(monkeypatch, dbf)
    init_db()
    ts = int(time.time())
    with sqlite3.connect(dbf) as c:
        c.execute("PRAGMA foreign_keys=ON;")
        c.execute(
            """
            INSERT INTO background_jobs(tenant_id, job_type, payload_json, status, created_at, updated_at)
            VALUES (NULL, 'stream_collect', '{}', 'completed', ?, ?)
            """,
            (ts, ts),
        )
        jid = int(c.execute("SELECT last_insert_rowid()").fetchone()[0])
        upsert_stream_job_artifact_index(
            c,
            job_id=jid,
            parquet_path="/tmp/out.parquet",
            summary_json_path="/tmp/sum.json",
            state_json_path="/tmp/state.json",
            progress_json_path="/tmp/prog.json",
        )
        c.commit()
    con = sqlite3.connect(dbf)
    row = con.execute(
        "SELECT parquet_path, summary_json_path, state_json_path, progress_json_path FROM stream_job_artifact_index WHERE job_id = ?",
        (jid,),
    ).fetchone()
    assert row[0] == "/tmp/out.parquet"
    assert row[1] == "/tmp/sum.json"
    assert row[2] == "/tmp/state.json"
    assert row[3] == "/tmp/prog.json"
    con.close()
