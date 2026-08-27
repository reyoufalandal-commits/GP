from __future__ import annotations

import numpy as np

from hawk_eye.open_set import nearest_prototype_min_distance


def test_nearest_prototype_distance() -> None:
    Xt = np.array([[0.0, 0.0], [10.0, 10.0]], dtype=np.float64)
    means = np.array([[0.0, 0.0], [5.0, 5.0]], dtype=np.float64)
    d = nearest_prototype_min_distance(Xt, means)
    assert d[0] < 1e-6
    assert d[1] > 1.0
