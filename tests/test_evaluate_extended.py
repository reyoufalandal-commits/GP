from __future__ import annotations

import numpy as np

from hawk_eye.evaluate_extended import binary_benign_attack_metrics, multiclass_macro_micro


def test_multiclass_macro_micro() -> None:
    y_t = np.array(["a", "a", "b", "b"])
    y_p = np.array(["a", "b", "b", "b"])
    out = multiclass_macro_micro(y_t, y_p)
    assert "macro_avg" in out
    assert "per_class" in out


def test_binary_benign_metrics() -> None:
    y = np.array(["B", "B", "A", "A"])
    score = np.array([0.1, 0.2, 0.9, 0.8])
    out = binary_benign_attack_metrics(y, score, benign_label="B")
    assert "roc_auc" in out
    assert "pr_auc" in out
