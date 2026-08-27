from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hawk_eye.backend.db import db_path

DEFAULT_BINARY = "artifacts/hawk-eye-binary"
DEFAULT_SUPERVISED = "artifacts/current"
DEFAULT_ANOMALY = "artifacts/current_anomaly"
DEFAULT_FUSION_FILE = "reports/thresholds_fusion_selected.json"
UNSW_PROFILES_FILE = "reports/unsw_external_profiles.json"


def project_root() -> Path:
    return db_path().resolve().parents[2]


def _read_json_if_exists(rel: str) -> dict[str, Any]:
    p = project_root() / rel
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def load_unsw_profiles() -> dict[str, Any]:
    return _read_json_if_exists(UNSW_PROFILES_FILE)


def default_fusion_kwargs() -> dict[str, float]:
    data = _read_json_if_exists(DEFAULT_FUSION_FILE)
    return {
        "min_p_attack_known": float(data.get("min_p_attack_known", 0.70)),
        "min_szd_uncertain": float(data.get("min_szd_uncertain", 70.0)),
        "min_open_set_uncertain": float(data.get("min_open_set_uncertain", 0.60)),
    }


def fusion_kwargs_for_profile(profile: str, profiles: dict[str, Any] | None = None) -> dict[str, float]:
    """
    Map UNSW profile name to fuse_decisions kwargs.
    `profile` is 'balanced' or 'high_recall'.
    """
    profiles = profiles if profiles is not None else load_unsw_profiles()
    base = default_fusion_kwargs()
    if profile == "balanced":
        p = profiles.get("balanced_profile") or {}
        t = p.get("thresholds") or {}
        if "open_set_ood_score" in t:
            base["min_open_set_uncertain"] = float(t["open_set_ood_score"])
        if "suspected_zero_day_pct" in t:
            base["min_szd_uncertain"] = float(t["suspected_zero_day_pct"])
        return base
    if profile == "high_recall":
        p = profiles.get("high_recall_profile") or {}
        ct = p.get("chosen_threshold")
        if ct is not None:
            base["min_p_attack_known"] = float(ct)
        base["min_open_set_uncertain"] = min(base["min_open_set_uncertain"], 0.50)
        base["min_szd_uncertain"] = min(base["min_szd_uncertain"], 55.0)
        return base
    return base


def resolve_artifact_dirs(
    req_binary: str | None,
    req_supervised: str | None,
    req_anomaly: str | None,
    settings_row: dict[str, Any] | None,
) -> tuple[str, str, str]:
    """Request body overrides DB overrides defaults."""
    s_bin = settings_row.get("binary_dir") if settings_row else None
    s_sup = settings_row.get("supervised_dir") if settings_row else None
    s_ano = settings_row.get("anomaly_dir") if settings_row else None
    return (
        req_binary or s_bin or DEFAULT_BINARY,
        req_supervised or s_sup or DEFAULT_SUPERVISED,
        req_anomaly or s_ano or DEFAULT_ANOMALY,
    )
