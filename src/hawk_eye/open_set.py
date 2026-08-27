"""
Open-set style scores: distance to nearest class mean in preprocessed feature space.

This is a lightweight proxy for OOD / unknown-class behavior — not a calibrated
probability of a zero-day exploit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from hawk_eye.bundle import load as load_bundle
from hawk_eye.features import align_columns_strict
from hawk_eye.io import read_table, write_table
from hawk_eye.paths import resolve_model_dir

PROTOTYPES_NAME = "open_set_prototypes.npz"
META_NAME = "open_set_meta.json"


def fit_and_save_prototypes(
    bundle_dir: str | Path,
    Xt: np.ndarray,
    y: np.ndarray,
    *,
    classes: np.ndarray,
) -> None:
    """Save per-class mean vectors (rows of Xt) for distance-based scoring."""
    p = Path(bundle_dir)
    means: list[np.ndarray] = []
    cls_list: list[str] = []
    for c in classes:
        mask = y == c
        if not np.any(mask):
            continue
        cls_list.append(str(c))
        means.append(np.asarray(Xt[mask].mean(axis=0), dtype=np.float64))
    if not means:
        return
    stacked = np.stack(means, axis=0)
    np.savez_compressed(p / PROTOTYPES_NAME, means=stacked, classes=np.array(cls_list, dtype=object))
    (p / META_NAME).write_text(json.dumps({"n_classes": len(cls_list), "classes": cls_list}, indent=2))


def load_prototypes(bundle_dir: Path) -> tuple[np.ndarray, np.ndarray] | None:
    proto = bundle_dir / PROTOTYPES_NAME
    if not proto.exists():
        return None
    z = np.load(proto, allow_pickle=True)
    return z["means"], z["classes"]


def nearest_prototype_min_distance(Xt: np.ndarray, means: np.ndarray) -> np.ndarray:
    """Euclidean distance to nearest class mean (lower = closer to some known class)."""
    # Xt: (n, d), means: (k, d)
    d2 = np.sum((Xt[:, None, :] - means[None, :, :]) ** 2, axis=2)
    return np.sqrt(np.min(d2, axis=1))


def score_open_set_dataframe(
    df: pd.DataFrame,
    *,
    bundle_dir: str | Path | None = None,
) -> pd.DataFrame:
    bdir = Path(resolve_model_dir(model_dir=bundle_dir))
    bundle = load_bundle(bdir)
    loaded = load_prototypes(bdir)
    if loaded is None:
        raise FileNotFoundError(
            f"No {PROTOTYPES_NAME} in bundle. Train with --save-open-set-prototypes."
        )
    means, _classes = loaded
    Xa = align_columns_strict(df, bundle.feature_columns)
    Xt = bundle.preprocessor.transform(Xa)
    if hasattr(Xt, "toarray"):
        Xt = Xt.toarray()
    Xt = np.asarray(Xt, dtype=np.float64)
    dist = nearest_prototype_min_distance(Xt, means)
    out = pd.DataFrame(
        {
            "open_set_nearest_distance": dist,
            "open_set_ood_score": _minmax_inv(dist),
        }
    )
    return out


def _minmax_inv(dist: np.ndarray) -> np.ndarray:
    """Higher = more OOD-like (heuristic), in [0,1] within batch."""
    if len(dist) == 0:
        return dist
    lo, hi = float(np.min(dist)), float(np.max(dist))
    if hi - lo < 1e-12:
        return np.zeros_like(dist)
    return (dist - lo) / (hi - lo)


def main() -> int:
    ap = argparse.ArgumentParser(description="Add open-set distance columns using bundle prototypes.")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--model-dir", default=None)
    args = ap.parse_args()

    df = read_table(args.input)
    extra = score_open_set_dataframe(df, bundle_dir=args.model_dir)
    out = pd.concat([df.reset_index(drop=True), extra], axis=1)
    write_table(out, args.output)
    print(json.dumps({"rows": len(out), "output": str(Path(args.output).resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
