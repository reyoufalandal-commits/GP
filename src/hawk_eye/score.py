from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from hawk_eye.bundle import Bundle, load as load_bundle
from hawk_eye.features import align_columns_strict
from hawk_eye.io import read_table, write_table
from hawk_eye.paths import resolve_model_dir


def _sanitize_class_name_for_column(name: str) -> str:
    """Parquet-safe fragment for per-class probability column names."""
    s = re.sub(r"[^A-Za-z0-9_]+", "_", str(name).strip())
    if not s:
        s = "cls"
    if s[0].isdigit():
        s = "c_" + s
    return s[:120]


def _unique_proba_column_names(classes: np.ndarray, n_classes: int) -> list[str]:
    used: set[str] = set()
    out: list[str] = []
    for i in range(n_classes):
        base = "p_" + _sanitize_class_name_for_column(str(classes[i]))
        name = base
        j = 0
        while name in used:
            j += 1
            name = f"{base}_{j}"
        used.add(name)
        out.append(name)
    return out


def build_score_dataframe(
    df: pd.DataFrame,
    *,
    bundle_dir: str | Path | None = None,
    predictions: bool = False,
    proba_all: bool = False,
    proba_max: bool = False,
) -> pd.DataFrame:
    """
    Score rows using a supervised bundle. Extra columns in df (e.g. Label) are ignored.
    """
    bdir = resolve_model_dir(model_dir=bundle_dir)
    bundle = load_bundle(bdir)
    X_aligned = align_columns_strict(df, bundle.feature_columns)
    Xt = bundle.preprocessor.transform(X_aligned)
    model = bundle.model

    out: dict[str, Any] = {}

    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(Xt)
        classes = getattr(model, "classes_", None)
        if bundle.config.get("binary_benign_vs_attack") and classes is not None:
            cl = [str(c) for c in classes]
            if "Attack" in cl:
                ai = cl.index("Attack")
                out["p_attack"] = proba[:, ai]
                out["score"] = proba[:, ai]
            else:
                out["score"] = proba[:, 1] if proba.shape[1] >= 2 else proba[:, 0]
        elif proba.shape[1] >= 2:
            out["score"] = proba[:, 1]
        else:
            out["score"] = proba[:, 0]
        if proba_max:
            out["proba_max"] = np.max(proba, axis=1)
        if proba_all:
            if classes is None or len(classes) != proba.shape[1]:
                classes = np.array([f"class_{i}" for i in range(proba.shape[1])], dtype=object)
            names = _unique_proba_column_names(np.asarray(classes), proba.shape[1])
            for j, col in enumerate(names):
                out[col] = proba[:, j]
    elif hasattr(model, "decision_function"):
        s = model.decision_function(Xt)
        out["score"] = np.asarray(s).reshape(-1)
    else:
        pred = model.predict(Xt)
        out["prediction"] = np.asarray(pred).reshape(-1)

    if predictions and hasattr(model, "predict"):
        out["prediction"] = model.predict(Xt)

    df_out = pd.DataFrame(out)
    df_out["model_version"] = bundle.config.get("bundle_version", "")
    return df_out


def _score_array(bundle: Bundle, X: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Legacy single-column score for backward compatibility."""
    X_aligned = align_columns_strict(X, bundle.feature_columns)
    Xt = bundle.preprocessor.transform(X_aligned)

    model = bundle.model
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(Xt)
        classes = getattr(model, "classes_", None)
        if bundle.config.get("binary_benign_vs_attack") and classes is not None:
            cl = [str(c) for c in classes]
            if "Attack" in cl:
                ai = cl.index("Attack")
                return proba[:, ai], ["score"]
        if proba.shape[1] >= 2:
            return proba[:, 1], ["score"]
        return proba[:, 0], ["score"]

    if hasattr(model, "decision_function"):
        s = model.decision_function(Xt)
        return np.asarray(s).reshape(-1), ["score"]

    pred = model.predict(Xt)
    return np.asarray(pred).reshape(-1), ["prediction"]


def score_dataframe(df: pd.DataFrame, *, bundle_dir: str | Path | None = None) -> pd.DataFrame:
    bdir = resolve_model_dir(model_dir=bundle_dir)
    bundle = load_bundle(bdir)
    scores, cols = _score_array(bundle, df)
    out = pd.DataFrame({cols[0]: scores})
    out["model_version"] = bundle.config.get("bundle_version", "")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="CSV/Parquet with feature columns (Label allowed).")
    ap.add_argument("--output", required=True, help="Output CSV/Parquet for scores.")
    ap.add_argument("--model-dir", default=None, help="Bundle directory override.")
    ap.add_argument("--id-col", default=None, help="Optional ID column to pass through to output.")
    ap.add_argument(
        "--predictions",
        action="store_true",
        help="Include predicted class label column (multiclass/supervised).",
    )
    ap.add_argument(
        "--proba-all",
        action="store_true",
        help="Include per-class probability columns (p_<class>). Requires predict_proba.",
    )
    ap.add_argument(
        "--proba-max",
        action="store_true",
        help="Include proba_max column (max softmax probability).",
    )
    ap.add_argument(
        "--jsonl",
        action="store_true",
        help="Also write results.jsonl next to --output (dashboard-ready).",
    )
    ap.add_argument(
        "--emit-run-summary",
        default=None,
        help="Write JSON with row count and score percentiles to this path.",
    )
    args = ap.parse_args()

    X = read_table(args.input)
    out = build_score_dataframe(
        X,
        bundle_dir=args.model_dir,
        predictions=args.predictions,
        proba_all=args.proba_all,
        proba_max=args.proba_max,
    )

    if args.id_col and args.id_col in X.columns:
        out.insert(0, args.id_col, X[args.id_col].astype(str))

    write_table(out, args.output)

    if args.emit_run_summary:
        bdir = resolve_model_dir(model_dir=args.model_dir)
        bundle = load_bundle(bdir)
        summ: dict[str, Any] = {
            "rows": len(out),
            "output": str(Path(args.output).resolve()),
            "model_version": bundle.config.get("bundle_version", ""),
            "feature_columns_hash": bundle.config.get("feature_columns_hash", ""),
        }
        if "score" in out.columns:
            s = out["score"].to_numpy()
            summ["score_p50"] = float(np.percentile(s, 50))
            summ["score_p99"] = float(np.percentile(s, 99))
        if "proba_max" in out.columns:
            pm = out["proba_max"].to_numpy()
            summ["proba_max_p50"] = float(np.percentile(pm, 50))
        Path(args.emit_run_summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.emit_run_summary).write_text(json.dumps(summ, indent=2))

    if args.jsonl:
        jsonl_path = Path(args.output).with_suffix("").with_name("results.jsonl")
        with jsonl_path.open("w") as f:
            for i in range(len(out)):
                row = out.iloc[i].to_dict()
                f.write(json.dumps(row) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
