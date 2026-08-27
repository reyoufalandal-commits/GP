"""Tests for lab stream config artifact writers."""
from __future__ import annotations

import json
from pathlib import Path

from hawk_eye.lab_stream_config import write_stream_lab_artifacts, write_stream_job_config_artifact


def test_write_stream_lab_artifacts(tmp_path: Path) -> None:
    conn = tmp_path / "lab" / "sim_conn.log"
    conn.parent.mkdir(parents=True)
    conn.write_text("x")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='t'\n")
    out = write_stream_lab_artifacts(
        conn_log_path=conn,
        scenario="mixed",
        line_count=3,
        repo_root=tmp_path,
        config_dir=tmp_path / "data" / "lab",
    )
    js = json.loads(Path(out["json"]).read_text(encoding="utf-8"))
    assert js["conn_log_path"] == str(conn.resolve())
    assert js["detection_settings_patch"]["active_dual_mode"] == "stream"
    assert Path(out["env_sh"]).read_text(encoding="utf-8").startswith("# Generated")


def test_write_stream_job_config_artifact(tmp_path: Path) -> None:
    p = write_stream_job_config_artifact(
        job_id=7,
        payload={"conn_log_path": "/a/conn.log", "fusion": {"x": 1}},
        summary={"rows_scored": 2},
        stream_sessions_dir=tmp_path,
    )
    assert p is not None
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["job_id"] == 7
    assert data["summary"]["rows_scored"] == 2
