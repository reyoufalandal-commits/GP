"""Argon2id password hashing with legacy SHA-256 verification for migration."""
from __future__ import annotations

import hashlib
import os

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher()


def hash_password(raw: str) -> str:
    return _ph.hash(raw)


def verify_password(stored_hash: str, raw: str) -> tuple[bool, bool]:
    """
    Verify password against stored hash.

    Returns (valid, needs_rehash) where needs_rehash is True if the row should be
    updated to a new Argon2 hash (legacy SHA-256 match, or Argon2 rehash).
    """
    if stored_hash.startswith("$argon2"):
        try:
            _ph.verify(stored_hash, raw)
            return True, _ph.check_needs_rehash(stored_hash)
        except VerifyMismatchError:
            return False, False
    legacy = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if legacy == stored_hash:
        return True, True
    return False, False


def legacy_sha256_hex(raw: str) -> str:
    """Test-only helper matching the old storage format."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def api_key_hash(raw_key: str) -> str:
    """
    Hash an API key for storage and lookup.

    If HAWK_EYE_API_KEY_PEPPER is set, it is prepended to the raw key before hashing
    (existing rows without pepper remain valid only when pepper is unset).
    """
    pepper = os.environ.get("HAWK_EYE_API_KEY_PEPPER", "")
    material = (pepper + raw_key).encode("utf-8")
    return hashlib.sha256(material).hexdigest()
