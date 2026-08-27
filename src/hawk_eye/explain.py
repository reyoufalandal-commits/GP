from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from hawk_eye.bundle import Bundle, load as load_bundle
from hawk_eye.features import align_columns_strict
from hawk_eye.redact import redact_obj


@dataclass(frozen=True)
class FeatureContribution:
    name: str
    value: float
    contribution: float


def top_linear_contributions(
    *,
    bundle: Bundle,
    row: pd.Series,
    top_k: int = 8,
) -> list[FeatureContribution]:
    """
    Deterministic, non-LLM explanation helper.

    If the model is linear (`coef_`), we compute per-feature contributions as:
      contribution_i = coef_i * x_i

    This is computed in the model's *post-preprocessing* feature space for the numeric-only
    pipeline used by default in `train.py`.
    """
    X = pd.DataFrame([row.to_dict()])
    X = align_columns_strict(X, bundle.feature_columns)
    Xt = bundle.preprocessor.transform(X)

    model = bundle.model
    if not hasattr(model, "coef_"):
        return []

    coef = np.asarray(model.coef_)
    if coef.ndim == 2 and coef.shape[0] >= 1:
        coef = coef[0]
    coef = coef.reshape(-1)

    x_vec = np.asarray(Xt).reshape(-1)
    n = min(len(coef), len(x_vec))
    contrib = coef[:n] * x_vec[:n]

    # In our default pipeline, each input numeric column maps 1:1 after StandardScaler.
    names = bundle.feature_columns[:n]
    pairs = [
        FeatureContribution(name=names[i], value=float(row[names[i]]), contribution=float(contrib[i]))
        for i in range(n)
        if names[i] in row
    ]
    pairs.sort(key=lambda p: abs(p.contribution), reverse=True)
    return pairs[:top_k]


def explain_row_from_records(
    *,
    bundle_dir: str | Path,
    row_dict: dict[str, Any],
    row_index: int = 0,
    top_k: int = 8,
    redact: bool = True,
) -> dict[str, Any]:
    """
    Same explain JSON shape as :func:`explain_row`, but from one in-memory feature row
    (e.g. the same dict sent to ``POST /api/v1/detections/score``). Extra keys not in
    the bundle contract are ignored by ``align_columns_strict`` inside
    ``top_linear_contributions``; missing required feature columns raise ``ValueError``.
    """
    bundle = load_bundle(bundle_dir)
    df = pd.DataFrame([row_dict])
    row = df.iloc[0]
    top = top_linear_contributions(bundle=bundle, row=row, top_k=top_k)
    payload: dict[str, Any] = {
        "model_version": bundle.config.get("bundle_version", ""),
        "row_index": row_index,
        "top_features": [c.__dict__ for c in top],
    }
    return redact_obj(payload) if redact else payload


def explain_row(
    *,
    bundle_dir: str | Path,
    features_csv: str | Path,
    row_index: int = 0,
    top_k: int = 8,
    redact: bool = True,
) -> dict[str, Any]:
    bundle = load_bundle(bundle_dir)
    df = pd.read_csv(features_csv)
    if row_index < 0 or row_index >= len(df):
        raise IndexError(f"row_index out of range: {row_index}")

    row = df.iloc[row_index]
    top = top_linear_contributions(bundle=bundle, row=row, top_k=top_k)

    payload: dict[str, Any] = {
        "model_version": bundle.config.get("bundle_version", ""),
        "row_index": row_index,
        "top_features": [c.__dict__ for c in top],
    }
    return redact_obj(payload) if redact else payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True, help="Bundle directory.")
    ap.add_argument("--features-csv", required=True, help="CSV containing feature columns.")
    ap.add_argument("--row-index", type=int, default=0)
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--out", default=None, help="Optional path to write explain.json.")
    args = ap.parse_args()

    payload = explain_row(
        bundle_dir=args.model_dir,
        features_csv=args.features_csv,
        row_index=args.row_index,
        top_k=args.top_k,
        redact=True,
    )
    s = json.dumps(payload, indent=2)
    print(s)

    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

