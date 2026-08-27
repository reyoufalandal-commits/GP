"""Versioning metadata for fusion thresholds and profile JSON on disk."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from hawk_eye.backend.detection_resolution import (
    DEFAULT_FUSION_FILE,
    UNSW_PROFILES_FILE,
    fusion_kwargs_for_profile,
    project_root,
)


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def fusion_policy_snapshot(*, profile: str) -> dict[str, Any]:
    """
    Resolved fusion kwargs plus content hashes of source JSON files.
    Use for governance, release notes, and reproducibility.
    """
    root = project_root()
    fusion_path = root / DEFAULT_FUSION_FILE
    profiles_path = root / UNSW_PROFILES_FILE
    resolved = fusion_kwargs_for_profile(profile)
    fusion_hash = _sha256_file(fusion_path)
    profiles_hash = _sha256_file(profiles_path)
    composite = hashlib.sha256(
        json.dumps(
            {"profile": profile, "resolved": resolved, "fusion": fusion_hash, "profiles": profiles_hash},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return {
        "active_unsw_profile": profile,
        "source_files": {
            "thresholds_fusion_selected": {
                "relative_path": DEFAULT_FUSION_FILE,
                "exists": fusion_path.exists(),
                "sha256": fusion_hash,
            },
            "unsw_external_profiles": {
                "relative_path": UNSW_PROFILES_FILE,
                "exists": profiles_path.exists(),
                "sha256": profiles_hash,
            },
        },
        "resolved_fusion_kwargs": resolved,
        "policy_composite_sha256": composite,
    }
