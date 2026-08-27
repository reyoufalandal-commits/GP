from __future__ import annotations


def parse_duration_to_seconds(value: str | int, *, max_seconds: int = 86400) -> int:
    """
    Parse human-readable duration into seconds.
    Supports: 30s, 1m, 2m, 1h, 1d, or plain integer seconds (e.g. "120" or 120).
    Default max is 24 hours; pass max_seconds to allow longer windows (e.g. 7 days).
    """
    if isinstance(value, int):
        sec = value
    else:
        v = str(value).strip().lower().replace(" ", "")
        if not v:
            raise ValueError("empty duration")
        if v.isdigit():
            sec = int(v)
        elif len(v) >= 2 and v[:-1].isdigit():
            num = int(v[:-1])
            suf = v[-1]
            if suf == "s":
                sec = num
            elif suf == "m":
                sec = num * 60
            elif suf == "h":
                sec = num * 3600
            elif suf == "d":
                sec = num * 86400
            else:
                raise ValueError(f"invalid duration suffix in {value!r}")
        else:
            raise ValueError(f"invalid duration: {value!r}")
    if sec < 1:
        raise ValueError("duration must be at least 1 second")
    if sec > max_seconds:
        raise ValueError(f"duration exceeds maximum of {max_seconds} seconds")
    return sec
