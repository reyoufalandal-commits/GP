"""Map multiclass labels to binary Benign vs Attack (case-insensitive benign set)."""
from __future__ import annotations

from typing import Any

import numpy as np

BINARY_BENIGN = "Benign"
BINARY_ATTACK = "Attack"


def _norm(s: Any) -> str:
    return str(s).strip().lower()


def to_benign_attack(y: np.ndarray, benign_labels: set[str]) -> np.ndarray:
    """Rows matching any string in benign_labels (case-insensitive) -> Benign; else Attack."""
    benign_l = {_norm(x) for x in benign_labels}
    out: list[str] = []
    for v in y:
        out.append(BINARY_BENIGN if _norm(v) in benign_l else BINARY_ATTACK)
    return np.array(out, dtype=object)


def default_benign_labels() -> set[str]:
    return {"Benign", "benign", "BENIGN"}
