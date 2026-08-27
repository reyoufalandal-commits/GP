from __future__ import annotations

from hawk_eye.backend.passwords import api_key_hash, hash_password, legacy_sha256_hex, verify_password


def test_argon2_roundtrip() -> None:
    h = hash_password("secret")
    assert h.startswith("$argon2")
    ok, rehash = verify_password(h, "secret")
    assert ok and not rehash


def test_argon2_wrong_password() -> None:
    h = hash_password("secret")
    ok, _ = verify_password(h, "other")
    assert not ok


def test_legacy_sha256_upgrade_flag() -> None:
    leg = legacy_sha256_hex("pw123")
    ok, needs = verify_password(leg, "pw123")
    assert ok and needs


def test_api_key_hash_empty_pepper_matches_legacy() -> None:
    import hashlib

    raw = "he_testkey"
    assert api_key_hash(raw) == hashlib.sha256(raw.encode("utf-8")).hexdigest()
