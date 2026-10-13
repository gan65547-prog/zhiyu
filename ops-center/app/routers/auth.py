from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import require_ops_user
from app.auth.token_service import create_access_token
from app.auth import user_store

router = APIRouter()


@router.post("/api/v1/auth/login")
async def login(body: dict) -> dict:
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "error": {"code": "INVALID_CREDENTIALS", "message": "用户名或密码不能为空"}},
        )
    user = user_store.USER_STORE.authenticate(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "error": {"code": "AUTH_FAILED", "message": "用户名或密码错误"}},
        )
    token = create_access_token(username=user.username, roles=user.roles)
    return {
        "success": True,
        "message": "ok",
        "data": {"access_token": token, "token_type": "Bearer", "expires_in": 3600},
    }


@router.get("/api/v1/auth/me")
async def me(current_user: Annotated[dict, Depends(require_ops_user)]) -> dict:
    return {"success": True, "message": "ok", "data": current_user}
