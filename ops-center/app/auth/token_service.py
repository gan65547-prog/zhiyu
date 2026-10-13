from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import jwt
from fastapi import HTTPException, status

from app.config import get_settings


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode())


def _sign_legacy_payload(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return _b64_encode(digest)


def _verify_legacy_token(token: str) -> dict[str, Any]:
    """兼容旧版自研 token（两段 base64url），仅用于平滑迁移。"""
    settings = get_settings()
    try:
        payload_text, sig = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_TOKEN") from exc
    expected_sig = _sign_legacy_payload(payload_text, settings.auth_secret_key)
    if not hmac.compare_digest(sig, expected_sig):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_TOKEN_SIGNATURE")
    try:
        payload = json.loads(_b64_decode(payload_text).decode())
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_TOKEN_PAYLOAD") from exc
    exp = int(payload.get("exp", 0))
    if exp <= int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="TOKEN_EXPIRED")
    return payload


def create_access_token(username: str, roles: list[str]) -> str:
    settings = get_settings()
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": username,
        "roles": roles,
        "iat": now,
        "exp": now + max(60, settings.auth_token_expire_seconds),
    }
    token = jwt.encode(payload, settings.auth_secret_key, algorithm="HS256")
    if isinstance(token, bytes):
        return token.decode("utf-8")
    return token


def verify_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    parts = token.split(".")
    if len(parts) == 3:
        try:
            payload = jwt.decode(
                token,
                settings.auth_secret_key,
                algorithms=["HS256"],
                options={"require": ["exp", "iat", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="TOKEN_EXPIRED") from exc
        except jwt.InvalidTokenError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_TOKEN") from exc
        return payload
    if len(parts) == 2:
        return _verify_legacy_token(token)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_TOKEN")
