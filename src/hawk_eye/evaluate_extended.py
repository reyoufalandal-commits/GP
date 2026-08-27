"""Extra metrics helpers for evaluate.py (fixed-FPR on benign, PR-AUC)."""
from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    auc,
    average_precision_score,
    precision_recall_fscore_support,
    roc_curve,
)


def multiclass_macro_micro(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    labels: list[Any] | np.ndarray | None = None,
) -> dict[str, Any]:
    if labels is None:
        labels_arr = np.unique(np.concatenate([np.asarray(y_true).ravel(), np.asarray(y_pred).ravel()]))
    else:
        labels_arr = np.asarray(labels)
    prec, rec, f1, sup = precision_recall_fscore_support(
        y_true, y_pred, average=None, zero_division=0, labels=labels_arr
    )
    out: dict[str, Any] = {"per_class": {}}
    lab = labels_arr
    for i, name in enumerate(lab):
        if i < len(f1):
            out["per_class"][str(name)] = {
                "precision": float(prec[i]),
                "recall": float(rec[i]),
                "f1": float(f1[i]),
                "support": int(sup[i]),
            }
    pm, rm, fm, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0
    )
    pw, rw, fw, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )
    out["macro_avg"] = {"precision": float(pm), "recall": float(rm), "f1": float(fm)}
    out["weighted_avg"] = {"precision": float(pw), "recall": float(rw), "f1": float(fw)}
    return out


def binary_benign_attack_metrics(
    y_true: np.ndarray,
    y_score_attack: np.ndarray,
    *,
    benign_label: str,
    target_fprs: tuple[float, ...] = (0.001, 0.01, 0.05),
) -> dict[str, Any]:
    """
    y_score_attack: score for "attack" (e.g. 1 - p(benign) or max proba of non-benign).
    """
    y_bin = (y_true != benign_label).astype(np.int32)
    fpr, tpr, thr = roc_curve(y_bin, y_score_attack)
    roc_auc = auc(fpr, tpr)
    pr_auc = average_precision_score(y_bin, y_score_attack)

    out: dict[str, Any] = {
        "roc_auc": float(roc_auc),
        "pr_auc": float(pr_auc),
        "thresholds_at_max_fpr": {},
    }
    for target in target_fprs:
        mask = fpr <= target
        if not np.any(mask):
            continue
        idx = np.where(mask)[0][-1]
        out["thresholds_at_max_fpr"][str(target)] = {
            "threshold": float(thr[idx]),
            "tpr": float(tpr[idx]),
            "fpr": float(fpr[idx]),
        }
    return out
