from __future__ import annotations

import json
import time
from pathlib import Path
from hawk_eye.backend.db import db_path, get_db, init_db
from hawk_eye.backend.job_artifacts_repo import upsert_stream_job_artifact_index
from hawk_eye.lab_stream_config import write_stream_job_config_artifact
from hawk_eye.live.dual_mode import run_stream_collect_duration


def _ts() -> int:
    return int(time.time())


def _session_root() -> Path:
    root = db_path().resolve().parents[2] / "data" / "stream_sessions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_stream_collect_job(job_id: int) -> None:
    """Background worker: timed Zeek conn.log collection + scoring (see POST /detections/stream-session)."""
    init_db()
    payload_json: str | None = None
    with get_db() as db:
        row = db.execute("SELECT * FROM background_jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return
        if str(row["status"]) != "pending":
            return
        db.execute(
            "UPDATE background_jobs SET status = 'running', updated_at = ? WHERE id = ?",
            (_ts(), job_id),
        )
        payload_json = str(row["payload_json"])
    payload = json.loads(payload_json)
    try:
        fusion = payload.get("fusion") or {}
        summary = run_stream_collect_duration(
            conn_log=payload["conn_log_path"],
            state_path=payload["state_path"],
            output_path=payload["output_path"],
            binary_dir=payload["binary_dir"],
            supervised_dir=payload["supervised_dir"],
            anomaly_dir=payload["anomaly_dir"],
            duration_seconds=float(payload["duration_seconds"]),
            poll_seconds=float(payload["poll_seconds"]),
            fusion_kwargs={k: float(v) for k, v in fusion.items()},
            alert_log_path=payload.get("alert_log_path"),
            webhook_url=payload.get("webhook_url"),
            webhook_only_known_attack=bool(payload.get("webhook_only_known_attack")),
            progress_path=payload.get("progress_path"),
        )
        session_root = _session_root()
        summary_path = session_root / f"job_{job_id}_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        write_stream_job_config_artifact(
            job_id=job_id,
            payload=payload,
            summary=summary,
            stream_sessions_dir=session_root,
        )
        out_p = Path(payload["output_path"]).resolve()
        state_p = Path(payload["state_path"]).resolve()
        prog_raw = payload.get("progress_path")
        prog_p = Path(str(prog_raw)).resolve() if prog_raw and str(prog_raw).strip() else None
        with get_db() as db:
            db.execute(
                "UPDATE background_jobs SET status = ?, result_path = ?, error = NULL, updated_at = ? WHERE id = ?",
                ("completed", str(summary_path.resolve()), _ts(), job_id),
            )
            upsert_stream_job_artifact_index(
                db,
                job_id=job_id,
                parquet_path=str(out_p),
                summary_json_path=str(summary_path.resolve()),
                state_json_path=str(state_p),
                progress_json_path=str(prog_p) if prog_p is not None else None,
            )
    except Exception as e:  # noqa: BLE001
        err = str(e)
        with get_db() as db:
            db.execute(
                "UPDATE background_jobs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                ("failed", err, _ts(), job_id),
            )
