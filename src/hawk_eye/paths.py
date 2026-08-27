from __future__ import annotations

import os
from pathlib import Path


def resolve_model_dir(
    *,
    model_dir: str | os.PathLike[str] | None,
    env_var: str = "HAWK_EYE_MODEL_DIR",
    default_current: str = "artifacts/current",
) -> Path:
    if model_dir is not None:
        return Path(model_dir).expanduser().resolve()

    env = os.environ.get(env_var)
    if env:
        return Path(env).expanduser().resolve()

    p = Path(default_current).expanduser().resolve()
    if p.exists():
        return p

    tried = [
        "--model-dir",
        f"env:{env_var}",
        default_current,
    ]
    raise FileNotFoundError(
        "Could not resolve model bundle directory. "
        f"Tried: {', '.join(tried)}. "
        "Set --model-dir or export HAWK_EYE_MODEL_DIR or create artifacts/current."
    )


def resolve_anomaly_dir(
    *,
    model_dir: str | os.PathLike[str] | None,
    env_var: str = "HAWK_EYE_ANOMALY_DIR",
    default_current: str = "artifacts/current_anomaly",
) -> Path:
    if model_dir is not None:
        return Path(model_dir).expanduser().resolve()

    env = os.environ.get(env_var)
    if env:
        return Path(env).expanduser().resolve()

    p = Path(default_current).expanduser().resolve()
    if p.exists():
        return p

    tried = ["--model-dir", f"env:{env_var}", default_current]
    raise FileNotFoundError(
        "Could not resolve anomaly bundle directory. "
        f"Tried: {', '.join(tried)}. "
        "Set --model-dir or export HAWK_EYE_ANOMALY_DIR or create artifacts/current_anomaly."
    )

