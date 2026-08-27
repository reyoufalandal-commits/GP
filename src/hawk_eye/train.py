from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline

from hawk_eye import __version__
from hawk_eye.bundle import save as save_bundle
from hawk_eye.features import FeatureSpec, infer_feature_columns, split_xy
from hawk_eye.io import read_table
from hawk_eye.labels_binary import default_benign_labels, to_benign_attack
from hawk_eye.open_set import fit_and_save_prototypes
from hawk_eye.preprocessing_supervised import build_numeric_preprocessor
from hawk_eye.supervised_estimators import (
    build_base_estimator,
    build_voting_soft_ensemble,
    compute_sample_weights_balanced,
    compute_sample_weights_rare_boost,
)


def _feature_hash(feature_columns: list[str]) -> str:
    return hashlib.sha256(json.dumps(feature_columns).encode("utf-8")).hexdigest()[:16]


def _build_pipeline(
    numeric_columns: list[str],
    *,
    logistic_class_weight: str | None = None,
    model_type: str = "logistic",
    n_classes_hint: int = 2,
    ensemble_include_lgbm: bool = False,
    ensemble_include_xgb: bool = False,
) -> Pipeline:
    pre = build_numeric_preprocessor(numeric_columns)
    if model_type == "ensemble_voting":
        try:
            clf = build_voting_soft_ensemble(
                logistic_class_weight=logistic_class_weight,
                include_lightgbm=ensemble_include_lgbm,
                include_xgboost=ensemble_include_xgb,
                n_classes_hint=n_classes_hint,
            )
        except ImportError as e:
            raise ImportError(
                "ensemble_voting requires optional deps. Install: pip install -e '.[benchmark]'"
            ) from e
    else:
        if model_type in ("lightgbm", "xgboost"):
            try:
                clf = build_base_estimator(
                    model_type,
                    logistic_class_weight=logistic_class_weight,
                    n_classes_hint=n_classes_hint,
                )
            except ImportError as e:
                raise ImportError(
                    f"model_type={model_type!r} requires optional deps. "
                    "Install: pip install -e '.[benchmark]'"
                ) from e
        else:
            clf = build_base_estimator(
                model_type,
                logistic_class_weight=logistic_class_weight,
                n_classes_hint=n_classes_hint,
            )
    return Pipeline(steps=[("preprocessor", pre), ("model", clf)])


def _maybe_sample_weight(
    y: np.ndarray,
    *,
    logistic_class_weight: str | None,
    model_type: str,
    ensemble_include_xgb: bool,
) -> np.ndarray | None:
    if logistic_class_weight != "balanced":
        return None
    if model_type == "xgboost" or (model_type == "ensemble_voting" and ensemble_include_xgb):
        return compute_sample_weights_balanced(y)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="CSV/Parquet with features + label column.")
    ap.add_argument("--label-col", default="label", help="Label column name in --data.")
    ap.add_argument(
        "--id-cols",
        default="",
        help="Comma-separated ID columns to drop (optional).",
    )
    ap.add_argument("--out", required=True, help="Output bundle directory (artifacts/hawk-eye-x.y.z).")
    ap.add_argument("--dataset-slug", default="", help="Pinned Kaggle slug for metadata (optional).")
    ap.add_argument(
        "--logistic-balanced",
        action="store_true",
        help="Use class_weight='balanced' / sample weights (helps rare classes).",
    )
    ap.add_argument(
        "--model-type",
        choices=(
            "logistic",
            "hist_gradient_boosting",
            "lightgbm",
            "xgboost",
            "ensemble_voting",
        ),
        default="logistic",
        help="Supervised learner; lightgbm/xgboost/ensemble need pip install -e '.[benchmark]'.",
    )
    ap.add_argument(
        "--ensemble-include-lightgbm",
        action="store_true",
        help="For ensemble_voting: add LightGBM (requires benchmark extra).",
    )
    ap.add_argument(
        "--ensemble-include-xgboost",
        action="store_true",
        help="For ensemble_voting: add XGBoost (requires benchmark extra).",
    )
    ap.add_argument(
        "--calibration-data",
        default=None,
        help="Optional CSV/Parquet (same schema as --data) for probability calibration after training.",
    )
    ap.add_argument(
        "--calibration-method",
        choices=("sigmoid", "isotonic"),
        default="sigmoid",
        help="Method for CalibratedClassifierCV (validation split only).",
    )
    ap.add_argument(
        "--save-open-set-prototypes",
        action="store_true",
        help="Save per-class mean vectors in preprocessor space for open-set distance (open_set_prototypes.npz).",
    )
    ap.add_argument(
        "--rare-weight-power",
        type=float,
        default=0.0,
        help="Extra rare-class sample weighting strength (0 disables; typical 0.3..1.0).",
    )
    ap.add_argument(
        "--binary-benign-vs-attack",
        action="store_true",
        help="Collapse all labels to two classes: Benign vs Attack (see --benign-label).",
    )
    ap.add_argument(
        "--benign-label",
        action="append",
        default=None,
        help="Label value treated as benign (repeatable). Used with --binary-benign-vs-attack. Default: Benign,benign,BENIGN",
    )
    args = ap.parse_args()

    df = read_table(args.data)
    id_cols = [c.strip() for c in args.id_cols.split(",") if c.strip()]
    spec = FeatureSpec(feature_columns=[], label_column=args.label_col, id_columns=id_cols)
    X_df, y = split_xy(df, spec)

    benign_set: set[str] = set(args.benign_label) if args.benign_label else default_benign_labels()
    if args.binary_benign_vs_attack:
        y = to_benign_attack(y, benign_set)

    feature_columns = infer_feature_columns(df, drop=[args.label_col, *id_cols])
    X_df = X_df[feature_columns]
    X_df = X_df.select_dtypes(include=[np.number])
    numeric_columns = list(X_df.columns)
    if not numeric_columns:
        raise ValueError(
            "No numeric feature columns after dropping label/IDs. "
            "Check column names and dtypes in your CSV."
        )
    feature_columns = numeric_columns

    classes_unique = np.unique(y)
    n_classes = len(classes_unique)
    if args.binary_benign_vs_attack and n_classes != 2:
        raise ValueError(
            f"Binary training needs exactly 2 classes after mapping; got {n_classes}: {list(classes_unique)}. "
            "Check --benign-label covers all benign strings in your data."
        )

    cw = "balanced" if args.logistic_balanced else None
    pipe = _build_pipeline(
        numeric_columns,
        logistic_class_weight=cw,
        model_type=args.model_type,
        n_classes_hint=n_classes,
        ensemble_include_lgbm=args.ensemble_include_lightgbm,
        ensemble_include_xgb=args.ensemble_include_xgboost,
    )

    sw = _maybe_sample_weight(
        y,
        logistic_class_weight=cw,
        model_type=args.model_type,
        ensemble_include_xgb=args.ensemble_include_xgboost,
    )
    if float(args.rare_weight_power) > 0:
        rare_sw = compute_sample_weights_rare_boost(y, power=float(args.rare_weight_power))
        sw = rare_sw if sw is None else (sw * rare_sw)
    fit_kw: dict[str, Any] = {}
    if sw is not None:
        fit_kw["model__sample_weight"] = sw

    pipe.fit(X_df, y, **fit_kw)

    preprocessor = pipe.named_steps["preprocessor"]
    clf = pipe.named_steps["model"]

    model_out: Any = clf
    calibrated = False
    if args.calibration_data:
        cdf = read_table(args.calibration_data)
        spec_c = FeatureSpec(feature_columns=[], label_column=args.label_col, id_columns=id_cols)
        Xc, yc = split_xy(cdf, spec_c)
        if args.binary_benign_vs_attack:
            yc = to_benign_attack(yc, benign_set)
        Xc = Xc[feature_columns]
        Xc = Xc.select_dtypes(include=[np.number])
        if list(Xc.columns) != feature_columns:
            raise ValueError("Calibration data numeric columns must match training feature columns.")
        Xt_cal = preprocessor.transform(Xc)
        cal = CalibratedClassifierCV(
            estimator=clf,
            cv="prefit",
            method=args.calibration_method,
        )
        cal.fit(Xt_cal, yc)
        model_out = cal
        calibrated = True

    out_dir = Path(args.out)
    fc_hash = _feature_hash(feature_columns)
    cfg: dict[str, Any] = {
        "bundle_version": __version__,
        "label_column": args.label_col,
        "id_columns": id_cols,
        "dataset_slug": args.dataset_slug,
        "classes": list(model_out.classes_),
        "logistic_class_weight": cw or "uniform",
        "sklearn_model_type": args.model_type,
        "feature_columns_hash": fc_hash,
        "calibrated": calibrated,
        "calibration_method": args.calibration_method if calibrated else None,
        "calibration_fit_data": str(Path(args.calibration_data).resolve()) if args.calibration_data else None,
        "binary_benign_vs_attack": bool(args.binary_benign_vs_attack),
        "benign_labels_for_binary": sorted(benign_set) if args.binary_benign_vs_attack else None,
        "rare_weight_power": float(args.rare_weight_power),
    }
    if args.model_type == "ensemble_voting":
        cfg["ensemble_include_lightgbm"] = args.ensemble_include_lightgbm
        cfg["ensemble_include_xgboost"] = args.ensemble_include_xgboost

    try:
        import lightgbm as lgb

        cfg["lightgbm_version"] = lgb.__version__
    except ImportError:
        pass
    try:
        import xgboost as xgb

        cfg["xgboost_version"] = xgb.__version__
    except ImportError:
        pass

    metadata = {
        "n_rows": int(df.shape[0]),
        "n_features": int(X_df.shape[1]),
    }

    save_bundle(
        bundle_dir=out_dir,
        model=model_out,
        preprocessor=preprocessor,
        feature_columns=feature_columns,
        config=cfg,
        metadata=metadata,
    )

    if args.save_open_set_prototypes:
        Xt_tr = preprocessor.transform(X_df)
        fit_and_save_prototypes(out_dir, Xt_tr, y, classes=model_out.classes_ if hasattr(model_out, "classes_") else clf.classes_)

    print(json.dumps({"bundle_dir": str(out_dir.resolve()), "feature_columns_hash": fc_hash}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
