from __future__ import annotations

import hashlib
import secrets

import bcrypt

_BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """使用 bcrypt 存储密码。"""
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")


def verify_password(password: str, stored: str) -> tuple[bool, str | None]:
    """
    校验密码。
    返回 (是否匹配, 若为旧版 SHA-256 且校验成功则为新的 bcrypt 哈希以便落库升级，否则 None)。
    """
    s = stored.strip()
    if s.startswith("$2a$") or s.startswith("$2b$") or s.startswith("$2y$"):
        try:
            ok = bcrypt.checkpw(password.encode("utf-8"), s.encode("ascii"))
            return ok, None
        except ValueError:
            return False, None

    # 旧版：SHA-256 十六进制（64 字符）
    if len(s) == 64 and all(c in "0123456789abcdefABCDEF" for c in s):
        legacy = hashlib.sha256(password.encode()).hexdigest()
        if secrets.compare_digest(legacy.lower(), s.lower()):
            return True, hash_password(password)
    return False, None
