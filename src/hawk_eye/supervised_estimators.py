"""
Factories for sklearn classifiers used by ``hawk_eye.train`` (optional LightGBM/XGBoost).
"""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression


def _lgbm_classifier(*, class_weight: str | None) -> Any:
    import lightgbm as lgb

    kw: dict = {
        "n_estimators": 400,
        "learning_rate": 0.05,
        "max_depth": -1,
        "num_leaves": 63,
        "min_child_samples": 20,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "random_state": 42,
        "verbosity": -1,
        "force_col_wise": True,
    }
    if class_weight:
        kw["class_weight"] = class_weight
    return lgb.LGBMClassifier(**kw)


def _xgb_classifier(*, class_weight: str | None, n_classes: int) -> Any:
    import xgboost as xgb

    kw: dict = {
        "n_estimators": 400,
        "learning_rate": 0.06,
        "max_depth": 8,
        "min_child_weight": 2,
        "subsample": 0.85,
        "colsample_bytree": 0.85,
        "random_state": 42,
        "n_jobs": -1,
        "eval_metric": "mlogloss",
    }
    est = xgb.XGBClassifier(**kw)
    # sample_weight for imbalance can be applied at fit time in train.py if needed
    if class_weight == "balanced" and n_classes > 0:
        # Caller may use sample_weight in fit; XGBoost 2.x supports no class_weight on constructor
        pass
    return est


def build_base_estimator(
    model_type: str,
    *,
    logistic_class_weight: str | None,
    n_classes_hint: int = 2,
) -> Any:
    if model_type == "logistic":
        lr_kw: dict = {"max_iter": 1000}
        if logistic_class_weight:
            lr_kw["class_weight"] = logistic_class_weight
        return LogisticRegression(**lr_kw)
    if model_type == "hist_gradient_boosting":
        hgb_kw: dict = {
            "max_iter": 400,
            "learning_rate": 0.06,
            "max_depth": 10,
            "max_leaf_nodes": 63,
            "min_samples_leaf": 15,
            "l2_regularization": 0.05,
            "random_state": 42,
            "early_stopping": True,
            "validation_fraction": 0.12,
            "n_iter_no_change": 20,
        }
        if logistic_class_weight:
            hgb_kw["class_weight"] = logistic_class_weight
        return HistGradientBoostingClassifier(**hgb_kw)
    if model_type == "lightgbm":
        return _lgbm_classifier(class_weight=logistic_class_weight)
    if model_type == "xgboost":
        return _xgb_classifier(class_weight=logistic_class_weight, n_classes=n_classes_hint)
    raise ValueError(f"Unknown model_type: {model_type!r}")


def build_voting_soft_ensemble(
    *,
    logistic_class_weight: str | None,
    include_lightgbm: bool,
    include_xgboost: bool,
    n_classes_hint: int,
) -> VotingClassifier:
    estimators: list[tuple[str, Any]] = [
        ("lr", build_base_estimator("logistic", logistic_class_weight=logistic_class_weight)),
        ("hgb", build_base_estimator("hist_gradient_boosting", logistic_class_weight=logistic_class_weight)),
    ]
    if include_lightgbm:
        estimators.append(("lgbm", build_base_estimator("lightgbm", logistic_class_weight=logistic_class_weight)))
    if include_xgboost:
        estimators.append(("xgb", build_base_estimator("xgboost", logistic_class_weight=logistic_class_weight, n_classes_hint=n_classes_hint)))
    return VotingClassifier(estimators=estimators, voting="soft", n_jobs=1)


def compute_sample_weights_balanced(y: np.ndarray) -> np.ndarray | None:
    """For XGBoost when class_weight cannot be set on the estimator."""
    classes, inv = np.unique(y, return_inverse=True)
    counts = np.bincount(inv)
    total = len(y)
    w_per_class = total / (len(classes) * counts.astype(np.float64))
    return w_per_class[inv]


def compute_sample_weights_rare_boost(
    y: np.ndarray,
    *,
    power: float = 0.5,
) -> np.ndarray:
    """
    Rare-class weighting with mean-normalized multipliers.

    power=0 disables effect (all weights ~= 1). Typical useful range: 0.3..1.0.
    """
    classes, inv = np.unique(y, return_inverse=True)
    counts = np.bincount(inv).astype(np.float64)
    total = float(len(y))
    base = total / (len(classes) * counts)
    # Smooth control over imbalance pressure.
    mult = np.power(base, float(power))
    w = mult[inv]
    return w / np.mean(w)
