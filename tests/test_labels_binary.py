from __future__ import annotations

import numpy as np

from hawk_eye.labels_binary import to_benign_attack


def test_to_benign_attack() -> None:
    y = np.array(["Benign", "DDoS", "benign", "FTP-Patator"])
    out = to_benign_attack(y, {"Benign", "benign"})
    assert list(out) == ["Benign", "Attack", "Benign", "Attack"]
