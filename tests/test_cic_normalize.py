from __future__ import annotations

import pandas as pd

from hawk_eye.cic_normalize import (
    build_alias_to_canonical,
    normalize_flow_dataframe,
)


def test_build_alias_maps_underscore_variant() -> None:
    feat = ["Flow Duration", "Protocol"]
    m = build_alias_to_canonical(feat)
    assert m["flow duration"] == "Flow Duration"
    assert m["flow_duration"] == "Flow Duration"


def test_normalize_renames_and_drops_flow_id() -> None:
    feat = ["Protocol", "Flow Duration"]
    df = pd.DataFrame(
        {
            "flow_id": [1, 2],
            "protocol": [6, 17],
            "FLOW_DURATION": [1.0, 2.0],
        }
    )
    out = normalize_flow_dataframe(df, feature_columns=feat)
    assert "flow_id" not in out.columns.str.lower().tolist()
    assert "Protocol" in out.columns
    assert "Flow Duration" in out.columns
