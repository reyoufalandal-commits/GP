from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LogoutRequest(BaseModel):
    token: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class ApiKeyCreate(BaseModel):
    name: str


class ExportJobCreate(BaseModel):
    job_type: str = Field(default="export_alerts_csv", description="export_alerts_csv | export_audit_json")


class TenantCreate(BaseModel):
    name: str


class AlertCreate(BaseModel):
    tenant_id: int | None = None
    severity: str = "medium"
    title: str
    decision_label: str = "AttackUncertain"
    payload: dict[str, Any] = Field(default_factory=dict)


class AlertStatusUpdate(BaseModel):
    status: str


class CaseCreate(BaseModel):
    tenant_id: int | None = None
    title: str
    priority: str = "medium"
    owner: str | None = None
    alert_id: int | None = None


class CaseUpdate(BaseModel):
    status: str
    owner: str | None = None


class CaseCommentCreate(BaseModel):
    comment: str


class CaseAssignCreate(BaseModel):
    assignee: str


class RuleCreate(BaseModel):
    name: str
    expression: str
    severity: str = "medium"
    enabled: bool = True
    tenant_id: int | None = None


class SuppressionCreate(BaseModel):
    target_type: str
    target_value: str
    reason: str
    until_ts: int | None = None
    tenant_id: int | None = None


class ScoreRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    binary_dir: str | None = None
    supervised_dir: str | None = None
    anomaly_dir: str | None = None


class ExplainRowRequest(BaseModel):
    """One feature row (supervised bundle contract). Optional dirs override DB defaults."""

    row: dict[str, Any]
    supervised_dir: str | None = None
    row_index: int = Field(0, ge=0)
    top_k: int = Field(8, ge=1, le=32)


class LlmFormatExplanationRequest(BaseModel):
    """Same shape as ``explain`` output; formatted server-side (see ``docs/llm.md``)."""

    explain: dict[str, Any]


class StreamIncidentReportRequest(BaseModel):
    """Completed ``stream_collect`` job id (see Live stream UI)."""

    job_id: int = Field(..., ge=1)


class DetectionSettingsPatch(BaseModel):
    active_dual_mode: Literal["stream", "batch"] | None = None
    active_unsw_profile: Literal["balanced", "high_recall"] | None = None
    binary_dir: str | None = None
    supervised_dir: str | None = None
    anomaly_dir: str | None = None
    conn_log_path: str | None = None
    stream_poll_seconds: float | None = Field(None, ge=0.5, le=120.0)
    stream_duration_default_seconds: int | None = Field(None, ge=1, le=86400)


class StreamSessionCreate(BaseModel):
    """Timed Zeek conn.log collection + scoring. Duration examples: 30s, 1m, 2m, 1h, 1d, or integer seconds."""

    duration: str | int
    conn_log_path: str | None = Field(None, description="Defaults to conn_log_path in detection settings if unset.")
    poll_seconds: float | None = Field(None, ge=0.5, le=120.0, description="Poll interval; defaults to settings or 2.0.")
    binary_dir: str | None = None
    supervised_dir: str | None = None
    anomaly_dir: str | None = None
    alert_log_path: str | None = None
    webhook_url: str | None = None
    webhook_only_known_attack: bool = Field(
        False,
        description="If true, webhook/alert_log rows are KnownAttack only (fewer posts than AttackUncertain+KnownAttack).",
    )


class StreamMarkdownExportBody(BaseModel):
    """Optional narrative to embed in Markdown export (e.g. prior LLM output from the UI)."""

    incident_markdown: str | None = None
