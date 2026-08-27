from __future__ import annotations

import json
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib


REQUIRED_FILES = {
    "model": "model.joblib",
    "preprocessor": "preprocessor.joblib",
    "feature_columns": "feature_columns.json",
    "config": "config.json",
}


@dataclass(frozen=True)
class Bundle:
    dir: Path
    model: Any
    preprocessor: Any
    feature_columns: list[str]
    config: dict[str, Any]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True))


def validate_bundle_dir(bundle_dir: Path) -> None:
    missing: list[str] = []
    for _, fname in REQUIRED_FILES.items():
        if not (bundle_dir / fname).exists():
            missing.append(fname)
    if missing:
        raise FileNotFoundError(
            f"Model bundle is missing required files: {missing}. "
            f"Bundle dir: {str(bundle_dir)}"
        )


def load(bundle_dir: str | Path) -> Bundle:
    p = Path(bundle_dir).expanduser().resolve()
    validate_bundle_dir(p)

    model = joblib.load(p / REQUIRED_FILES["model"])
    preprocessor = joblib.load(p / REQUIRED_FILES["preprocessor"])
    feature_columns = _read_json(p / REQUIRED_FILES["feature_columns"])
    config = _read_json(p / REQUIRED_FILES["config"])

    if not isinstance(feature_columns, list) or not all(
        isinstance(x, str) for x in feature_columns
    ):
        raise ValueError(
            f"{REQUIRED_FILES['feature_columns']} must be a JSON list of strings."
        )

    if not hasattr(preprocessor, "transform"):
        raise TypeError("Loaded preprocessor does not implement transform().")

    if not (
        hasattr(model, "predict")
        or hasattr(model, "decision_function")
        or hasattr(model, "predict_proba")
    ):
        raise TypeError("Loaded model does not look like a sklearn estimator.")

    return Bundle(
        dir=p,
        model=model,
        preprocessor=preprocessor,
        feature_columns=feature_columns,
        config=config,
    )


def save(
    *,
    bundle_dir: str | Path,
    model: Any,
    preprocessor: Any,
    feature_columns: list[str],
    config: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> Path:
    p = Path(bundle_dir).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, p / REQUIRED_FILES["model"])
    joblib.dump(preprocessor, p / REQUIRED_FILES["preprocessor"])
    _write_json(p / REQUIRED_FILES["feature_columns"], feature_columns)

    config_out = dict(config)
    config_out.setdefault("bundle_version", "0.1.0")
    config_out.setdefault("python", platform.python_version())
    config_out.setdefault("machine", platform.machine())
    _write_json(p / REQUIRED_FILES["config"], config_out)

    md = dict(metadata or {})
    _write_json(p / "metadata.json", md)

    validate_bundle_dir(p)
    return p

