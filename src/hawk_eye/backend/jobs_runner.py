from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

from hawk_eye.backend.db import db_path, get_db


def _ts() -> int:
    return int(time.time())


def _export_root() -> Path:
    root = db_path().resolve().parents[2]
    out = root / "data" / "exports"
    out.mkdir(parents=True, exist_ok=True)
    return out


def process_pending_jobs(limit: int = 10) -> int:
    """Run export jobs synchronously (SQLite-friendly). Returns count processed."""
    done = 0
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM background_jobs WHERE status = 'pending' ORDER BY id ASC LIMIT ?",
            (limit,),
        ).fetchall()
        for job in rows:
            jid = int(job["id"])
            jtype = str(job["job_type"])
            try:
                if jtype == "export_alerts_csv":
                    path = _run_export_alerts_csv(db, dict(job))
                elif jtype == "export_audit_json":
                    path = _run_export_audit_json(db, dict(job))
                else:
                    raise ValueError(f"unknown job_type {jtype}")
                db.execute(
                    "UPDATE background_jobs SET status = ?, result_path = ?, error = NULL, updated_at = ? WHERE id = ?",
                    ("completed", str(path), _ts(), jid),
                )
                done += 1
            except Exception as e:  # noqa: BLE001
                db.execute(
                    "UPDATE background_jobs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                    ("failed", str(e), _ts(), jid),
                )
                done += 1
    return done


def _run_export_alerts_csv(db: Any, job: dict[str, Any]) -> Path:
    tid = job.get("tenant_id")
    if tid is None:
        q = (
            "SELECT id, tenant_id, severity, title, decision_label, status, suppressed, created_at "
            "FROM alerts ORDER BY id DESC"
        )
        rows = db.execute(q).fetchall()
    else:
        q = (
            "SELECT id, tenant_id, severity, title, decision_label, status, suppressed, created_at "
            "FROM alerts WHERE tenant_id = ? OR tenant_id IS NULL ORDER BY id DESC"
        )
        rows = db.execute(q, (int(tid),)).fetchall()
    out = _export_root() / f"alerts_{job['id']}_{_ts()}.csv"
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "tenant_id", "severity", "title", "decision_label", "status", "suppressed", "created_at"])
        for r in rows:
            w.writerow(
                [
                    r["id"],
                    r["tenant_id"],
                    r["severity"],
                    r["title"],
                    r["decision_label"],
                    r["status"],
                    r["suppressed"],
                    r["created_at"],
                ]
            )
    return out


def _run_export_audit_json(db: Any, job: dict[str, Any]) -> Path:
    tid = job.get("tenant_id")
    if tid is None:
        q = "SELECT id, actor, action, payload_json, created_at, tenant_id FROM audit_events ORDER BY id DESC LIMIT 5000"
        rows = db.execute(q).fetchall()
    else:
        q = (
            "SELECT id, actor, action, payload_json, created_at, tenant_id FROM audit_events "
            "WHERE tenant_id = ? OR tenant_id IS NULL ORDER BY id DESC LIMIT 5000"
        )
        rows = db.execute(q, (int(tid),)).fetchall()
    data = [dict(r) for r in rows]
    out = _export_root() / f"audit_{job['id']}_{_ts()}.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out
