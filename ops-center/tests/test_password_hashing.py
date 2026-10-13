import hashlib

from app.auth.password_hashing import hash_password, verify_password


def test_bcrypt_roundtrip():
    h = hash_password("secret123")
    assert h.startswith("$2")
    ok, new_h = verify_password("secret123", h)
    assert ok is True
    assert new_h is None or new_h.startswith("$2")


def test_legacy_sha256_upgrades_to_bcrypt():
    legacy = hashlib.sha256("oldpass".encode()).hexdigest()
    ok, new_h = verify_password("oldpass", legacy)
    assert ok is True
    assert new_h is not None
    assert new_h.startswith("$2")
    ok2, _ = verify_password("oldpass", new_h)
    assert ok2 is True
