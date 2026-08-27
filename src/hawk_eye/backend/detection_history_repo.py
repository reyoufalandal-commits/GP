"""Persist and list API detection runs (score/triage/conn-log) for dashboard history."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

_MAX_DETAIL_LEN = 64_000


def insert_detection_history(
    conn: sqlite3.Connection,
    *,
    tenant_id: int | None,
    kind: str,
    row_count: int,
    detail: dict[str, Any] | None,
    actor_username: str,
) -> int:
    detail_json: str | None = None
    if detail is not None:
        s = json.dumps(detail, separators=(",", ":"), default=str)
        if len(s) > _MAX_DETAIL_LEN:
            s = json.dumps(
                {"_truncated": True, "preview": s[: _MAX_DETAIL_LEN - 80]},
                separators=(",", ":"),
            )
        detail_json = s
    cur = conn.execute(
        """
        INSERT INTO detection_history (tenant_id, kind, created_at, row_count, detail_json, actor_username)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            tenant_id,
            kind,
            int(time.time()),
            row_count,
            detail_json,
            actor_username,
        ),
    )
    return int(cur.lastrowid)
