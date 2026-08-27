from __future__ import annotations

import pandas as pd
import pytest

from hawk_eye.features import align_columns_strict


def test_align_columns_strict_ignores_extra_columns() -> None:
    df = pd.DataFrame({"a": [1.0], "b": [2.0], "Label": ["Benign"], "id": [99]})
    out = align_columns_strict(df, ["a", "b"])
    assert list(out.columns) == ["a", "b"]
    assert len(out) == 1


def test_align_columns_strict_still_errors_on_missing() -> None:
    df = pd.DataFrame({"a": [1.0]})
    with pytest.raises(ValueError, match="Missing"):
        align_columns_strict(df, ["a", "b"])
