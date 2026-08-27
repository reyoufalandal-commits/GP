from __future__ import annotations

import sqlite3
import time
from typing import Any

VALID_MODES = frozenset({"stream", "batch"})
VALID_PROFILES = frozenset({"balanced", "high_recall"})

SETTING_KEYS = (
    "active_dual_mode",
    "active_unsw_profile",
    "binary_dir",
    "supervised_dir",
    "anomaly_dir",
    "conn_log_path",
    "stream_poll_seconds",
    "stream_duration_default_seconds",
)


def _ts() -> int:
    return int(time.time())


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def get_global(conn: sqlite3.Connection) -> dict[str, Any] | None:
    return _row_to_dict(conn.execute("SELECT * FROM detection_settings WHERE tenant_id IS NULL").fetchone())


def get_for_tenant(conn: sqlite3.Connection, tenant_id: int) -> dict[str, Any] | None:
    return _row_to_dict(conn.execute("SELECT * FROM detection_settings WHERE tenant_id = ?", (tenant_id,)).fetchone())


def merge_effective(global_row: dict[str, Any] | None, tenant_row: dict[str, Any] | None) -> dict[str, Any]:
    g = global_row or {}
    t = tenant_row or {}
    out: dict[str, Any] = {}
    for k in SETTING_KEYS:
        tv = t.get(k)
        if tv is not None and str(tv).strip() != "":
            out[k] = tv
        elif k in g and g[k] is not None:
            out[k] = g[k]
    if "active_dual_mode" not in out:
        out["active_dual_mode"] = "batch"
    if "active_unsw_profile" not in out:
        out["active_unsw_profile"] = "balanced"
    for k in ("binary_dir", "supervised_dir", "anomaly_dir", "conn_log_path"):
        if k not in out:
            out[k] = None
    if "stream_poll_seconds" not in out:
        sp = g.get("stream_poll_seconds")
        out["stream_poll_seconds"] = float(sp) if sp is not None else 2.0
    else:
        out["stream_poll_seconds"] = float(out["stream_poll_seconds"])
    if "stream_duration_default_seconds" not in out:
        sd = g.get("stream_duration_default_seconds")
        out["stream_duration_default_seconds"] = int(sd) if sd is not None else 60
    else:
        out["stream_duration_default_seconds"] = int(out["stream_duration_default_seconds"])
    return out


def ensure_global_defaults(conn: sqlite3.Connection) -> None:
    n = conn.execute("SELECT COUNT(*) AS c FROM detection_settings WHERE tenant_id IS NULL").fetchone()
    if n and int(n["c"]) == 0:
        conn.execute(
            """
            INSERT INTO detection_settings(tenant_id, active_dual_mode, active_unsw_profile, binary_dir, supervised_dir, anomaly_dir, conn_log_path, stream_poll_seconds, stream_duration_default_seconds, updated_at)
            VALUES (NULL, 'batch', 'balanced', NULL, NULL, NULL, NULL, 2.0, 60, ?)
            """,
            (_ts(),),
        )


def _validate_effective(m: dict[str, Any]) -> None:
    if str(m.get("active_dual_mode", "batch")) not in VALID_MODES:
        raise ValueError("invalid active_dual_mode")
    if str(m.get("active_unsw_profile", "balanced")) not in VALID_PROFILES:
        raise ValueError("invalid active_unsw_profile")
    if m.get("stream_poll_seconds") is not None:
        p = float(m["stream_poll_seconds"])
        if not (0.5 <= p <= 120.0):
            raise ValueError("stream_poll_seconds must be between 0.5 and 120")
    if m.get("stream_duration_default_seconds") is not None:
        d = int(m["stream_duration_default_seconds"])
        if not (1 <= d <= 86400):
            raise ValueError("stream_duration_default_seconds must be 1..86400")


def upsert(
    conn: sqlite3.Connection,
    *,
    tenant_id: int | None,
    patch: dict[str, Any],
) -> None:
    """Apply PATCH semantics: only keys present in patch with non-None values update."""
    ensure_global_defaults(conn)
    g = get_global(conn)
    if g is None:
        raise RuntimeError("detection_settings global row missing")

    incoming: dict[str, Any] = {k: patch[k] for k in SETTING_KEYS if k in patch}
    for k in ("binary_dir", "supervised_dir", "anomaly_dir", "conn_log_path"):
        if k in incoming and incoming[k] == "":
            incoming[k] = None

    if tenant_id is None:
        m = dict(g)
        m.update(incoming)
        _validate_effective(m)
        conn.execute(
            """
            UPDATE detection_settings
            SET active_dual_mode = ?, active_unsw_profile = ?, binary_dir = ?, supervised_dir = ?, anomaly_dir = ?,
                conn_log_path = ?, stream_poll_seconds = ?, stream_duration_default_seconds = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                m["active_dual_mode"],
                m["active_unsw_profile"],
                m.get("binary_dir"),
                m.get("supervised_dir"),
                m.get("anomaly_dir"),
                m.get("conn_log_path"),
                float(m.get("stream_poll_seconds") or 2.0),
                int(m.get("stream_duration_default_seconds") or 60),
                _ts(),
                int(m["id"]),
            ),
        )
        return

    ex = get_for_tenant(conn, tenant_id)
    eff = merge_effective(g, ex)
    eff.update(incoming)
    _validate_effective(eff)
    if ex:
        conn.execute(
            """
            UPDATE detection_settings
            SET active_dual_mode = ?, active_unsw_profile = ?, binary_dir = ?, supervised_dir = ?, anomaly_dir = ?,
                conn_log_path = ?, stream_poll_seconds = ?, stream_duration_default_seconds = ?, updated_at = ?
            WHERE tenant_id = ?
            """,
            (
                eff["active_dual_mode"],
                eff["active_unsw_profile"],
                eff.get("binary_dir"),
                eff.get("supervised_dir"),
                eff.get("anomaly_dir"),
                eff.get("conn_log_path"),
                float(eff.get("stream_poll_seconds") or 2.0),
                int(eff.get("stream_duration_default_seconds") or 60),
                _ts(),
                tenant_id,
            ),
        )
    else:
        conn.execute(
            """
            INSERT INTO detection_settings(tenant_id, active_dual_mode, active_unsw_profile, binary_dir, supervised_dir, anomaly_dir, conn_log_path, stream_poll_seconds, stream_duration_default_seconds, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                eff["active_dual_mode"],
                eff["active_unsw_profile"],
                eff.get("binary_dir"),
                eff.get("supervised_dir"),
                eff.get("anomaly_dir"),
                eff.get("conn_log_path"),
                float(eff.get("stream_poll_seconds") or 2.0),
                int(eff.get("stream_duration_default_seconds") or 60),
                _ts(),
            ),
        )


def effective_for_tenant_id(conn: sqlite3.Connection, tenant_id: int | None) -> tuple[dict[str, Any], int | None]:
    """Effective settings for a tenant id (None = global defaults only)."""
    ensure_global_defaults(conn)
    g = get_global(conn)
    if tenant_id is None:
        return merge_effective(g, None), None
    t = get_for_tenant(conn, tenant_id)
    return merge_effective(g, t), tenant_id


def effective_for_user(conn: sqlite3.Connection, user: dict[str, Any]) -> tuple[dict[str, Any], int | None]:
    """
    Returns (effective_settings, scope_tenant_id) where scope is the tenant used for merge
    (None = only global).
    """
    tid = user.get("tenant_id")
    return effective_for_tenant_id(conn, int(tid) if tid is not None else None)
