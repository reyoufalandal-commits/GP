from __future__ import annotations

import pytest

from hawk_eye.backend.stream_duration import parse_duration_to_seconds


def test_parse_duration_examples() -> None:
    assert parse_duration_to_seconds("30s") == 30
    assert parse_duration_to_seconds("1m") == 60
    assert parse_duration_to_seconds("2m") == 120
    assert parse_duration_to_seconds("1h") == 3600
    assert parse_duration_to_seconds("1d") == 86400
    assert parse_duration_to_seconds(90) == 90
    assert parse_duration_to_seconds("90") == 90


def test_parse_duration_max() -> None:
    with pytest.raises(ValueError):
        parse_duration_to_seconds("90000h")
