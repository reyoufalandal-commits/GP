"""Optional password length enforcement for seeded and CLI-created users."""

from __future__ import annotations

import os


def min_password_length() -> int:
    raw = (os.environ.get("HAWK_EYE_PASSWORD_MIN_LENGTH") or "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return 8


def validate_new_password(password: str) -> None:
    """Raises ValueError if password does not meet policy."""
    n = min_password_length()
    if len(password) < n:
        raise ValueError(f"password must be at least {n} characters (set HAWK_EYE_PASSWORD_MIN_LENGTH to adjust)")
