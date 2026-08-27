from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 8


def db_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / "data" / "db" / "hawk_eye.db"


def _column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(r[1]) == col for r in rows)


def _migrate(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "detection_rules", "tenant_id"):
        conn.execute("ALTER TABLE detection_rules ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);")
    if not _column_exists(conn, "suppressions", "tenant_id"):
        conn.execute("ALTER TABLE suppressions ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);")
    if not _column_exists(conn, "audit_events", "tenant_id"):
        conn.execute("ALTER TABLE audit_events ADD COLUMN tenant_id INTEGER REFERENCES tenants(id);")
    if not _column_exists(conn, "detection_settings", "conn_log_path"):
        conn.execute("ALTER TABLE detection_settings ADD COLUMN conn_log_path TEXT;")
    if not _column_exists(conn, "detection_settings", "stream_poll_seconds"):
        conn.execute("ALTER TABLE detection_settings ADD COLUMN stream_poll_seconds REAL DEFAULT 2.0;")
    if not _column_exists(conn, "detection_settings", "stream_duration_default_seconds"):
        conn.execute("ALTER TABLE detection_settings ADD COLUMN stream_duration_default_seconds INTEGER DEFAULT 60;")


def init_db() -> None:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(p) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                tenant_id INTEGER,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                decision_label TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                suppressed INTEGER NOT NULL DEFAULT 0,
                rule_hits_json TEXT,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );
            """
        )
        if not _column_exists(conn, "alerts", "suppressed"):
            conn.execute("ALTER TABLE alerts ADD COLUMN suppressed INTEGER NOT NULL DEFAULT 0;")
        if not _column_exists(conn, "alerts", "rule_hits_json"):
            conn.execute("ALTER TABLE alerts ADD COLUMN rule_hits_json TEXT;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                owner TEXT,
                alert_id INTEGER,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id),
                FOREIGN KEY (alert_id) REFERENCES alerts(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                tenant_id INTEGER,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                issued_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                family_id TEXT NOT NULL,
                issued_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_hash TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                tenant_id INTEGER,
                created_at INTEGER NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS background_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER,
                job_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result_path TEXT,
                error TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS case_timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (case_id) REFERENCES cases(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS case_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                author TEXT NOT NULL,
                comment TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (case_id) REFERENCES cases(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS case_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                assignee TEXT NOT NULL,
                assigned_by TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (case_id) REFERENCES cases(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS detection_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                severity TEXT NOT NULL DEFAULT 'medium',
                expression TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                tenant_id INTEGER,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS suppressions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_type TEXT NOT NULL,
                target_value TEXT NOT NULL,
                reason TEXT NOT NULL,
                until_ts INTEGER,
                created_at INTEGER NOT NULL,
                tenant_id INTEGER,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS detection_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER UNIQUE,
                active_dual_mode TEXT NOT NULL DEFAULT 'batch',
                active_unsw_profile TEXT NOT NULL DEFAULT 'balanced',
                binary_dir TEXT,
                supervised_dir TEXT,
                anomaly_dir TEXT,
                conn_log_path TEXT,
                stream_poll_seconds REAL DEFAULT 2.0,
                stream_duration_default_seconds INTEGER DEFAULT 60,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scored_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER,
                row_id TEXT,
                timestamp TEXT,
                score REAL NOT NULL,
                label TEXT,
                model_version TEXT,
                raw_json TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_scored_events_tenant_created ON scored_events(tenant_id, created_at);"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stream_job_artifact_index (
                job_id INTEGER PRIMARY KEY,
                parquet_path TEXT,
                summary_json_path TEXT,
                state_json_path TEXT,
                progress_json_path TEXT,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (job_id) REFERENCES background_jobs(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS detection_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER,
                kind TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                row_count INTEGER NOT NULL DEFAULT 0,
                detail_json TEXT,
                actor_username TEXT NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenants(id)
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_detection_history_tenant_created ON detection_history(tenant_id, created_at);"
        )
        _migrate(conn)
        ds = conn.execute("SELECT COUNT(*) AS c FROM detection_settings WHERE tenant_id IS NULL").fetchone()
        if not ds or int(ds[0]) == 0:
            conn.execute(
                """
                INSERT INTO detection_settings(tenant_id, active_dual_mode, active_unsw_profile, binary_dir, supervised_dir, anomaly_dir, conn_log_path, stream_poll_seconds, stream_duration_default_seconds, updated_at)
                VALUES (NULL, 'batch', 'balanced', NULL, NULL, NULL, NULL, 2.0, 60, ?)
                """,
                (int(time.time()),),
            )
        conn.execute(
            "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        seeded = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
        if seeded is None:
            from hawk_eye.backend.passwords import hash_password

            env = os.environ.get("HAWK_EYE_ENV", "").lower().strip()
            init_pw = os.environ.get("HAWK_EYE_INITIAL_ADMIN_PASSWORD", "").strip()
            if env == "production" and not init_pw:
                pass
            else:
                raw_pw = init_pw if init_pw else "admin123"
                from hawk_eye.backend.password_policy import validate_new_password

                try:
                    validate_new_password(raw_pw)
                except ValueError as e:
                    raise RuntimeError(
                        f"Bootstrap password invalid: {e}. Set HAWK_EYE_INITIAL_ADMIN_PASSWORD to a compliant password."
                    ) from e
                conn.execute(
                    "INSERT INTO users(username, password_hash, role, tenant_id, created_at) VALUES(?, ?, ?, ?, ?)",
                    ("admin", hash_password(raw_pw), "admin", None, int(time.time())),
                )


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    init_db()
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
