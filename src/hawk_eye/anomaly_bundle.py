from __future__ import annotations

import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib


FILES = {
    "preprocessor": "preprocessor.joblib",
    "feature_columns": "feature_columns.json",
    "config": "config.json",
    "model": "model.joblib",
    "ae_weights": "ae_weights.pt",
}


@dataclass(frozen=True)
class AnomalyBundle:
    dir: Path
    preprocessor: Any
    feature_columns: list[str]
    config: dict[str, Any]
    model: Any | None
    ae_state_path: Path | None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True))


def validate_anomaly_bundle_dir(bundle_dir: Path) -> None:
    p = Path(bundle_dir)
    for key in ("preprocessor", "feature_columns", "config"):
        if not (p / FILES[key]).exists():
            raise FileNotFoundError(f"Missing {FILES[key]} in {p}")
    cfg = _read_json(p / FILES["config"])
    mt = cfg.get("model_type", "")
    if mt == "isolation_forest":
        if not (p / FILES["model"]).exists():
            raise FileNotFoundError(f"Missing {FILES['model']} for isolation_forest")
    elif mt == "autoencoder":
        if not (p / FILES["ae_weights"]).exists():
            raise FileNotFoundError(f"Missing {FILES['ae_weights']} for autoencoder")
    else:
        raise ValueError(f"Unknown or missing config.model_type: {mt!r}")


def load_anomaly_bundle(bundle_dir: str | Path) -> AnomalyBundle:
    p = Path(bundle_dir).expanduser().resolve()
    validate_anomaly_bundle_dir(p)
    preprocessor = joblib.load(p / FILES["preprocessor"])
    feature_columns = _read_json(p / FILES["feature_columns"])
    config = _read_json(p / FILES["config"])
    if not isinstance(feature_columns, list) or not all(isinstance(x, str) for x in feature_columns):
        raise ValueError("feature_columns.json must be a list of strings.")
    mt = config.get("model_type")
    model = None
    ae_path = None
    if mt == "isolation_forest":
        model = joblib.load(p / FILES["model"])
    elif mt == "autoencoder":
        ae_path = p / FILES["ae_weights"]
    return AnomalyBundle(
        dir=p,
        preprocessor=preprocessor,
        feature_columns=feature_columns,
        config=config,
        model=model,
        ae_state_path=ae_path,
    )


def save_anomaly_bundle(
    *,
    bundle_dir: str | Path,
    preprocessor: Any,
    feature_columns: list[str],
    config: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    sklearn_model: Any | None = None,
    ae_weights: Any | None = None,
) -> Path:
    p = Path(bundle_dir).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    joblib.dump(preprocessor, p / FILES["preprocessor"])
    _write_json(p / FILES["feature_columns"], feature_columns)
    cfg = dict(config)
    cfg.setdefault("python", platform.python_version())
    cfg.setdefault("machine", platform.machine())
    _write_json(p / FILES["config"], cfg)
    md = dict(metadata or {})
    _write_json(p / "metadata.json", md)

    mt = cfg.get("model_type")
    if mt == "isolation_forest":
        if sklearn_model is None:
            raise ValueError("sklearn_model required for isolation_forest")
        joblib.dump(sklearn_model, p / FILES["model"])
    elif mt == "autoencoder":
        if ae_weights is None:
            raise ValueError("ae_weights (state_dict or tensor module) required for autoencoder")
        import torch

        torch.save(ae_weights, p / FILES["ae_weights"])
    else:
        raise ValueError("config.model_type must be isolation_forest or autoencoder")

    validate_anomaly_bundle_dir(p)
    return p
