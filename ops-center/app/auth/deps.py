from __future__ import annotations

from typing import Annotated, FrozenSet

from fastapi import Depends, Header, HTTPException, status

from app.auth.token_service import verify_access_token
from app.auth import user_store

# 与 design 文档「运维中心独立部署方案」中的角色矩阵一致
CANONICAL_OPS_ROLES: FrozenSet[str] = frozenset(
    {"super_admin", "tenant_ops", "read_only_auditor"}
)
TENANT_WRITE_ROLES: FrozenSet[str] = frozenset({"super_admin", "tenant_ops"})


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MISSING_AUTHORIZATION")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_AUTHORIZATION_SCHEME")
    token = authorization[len(prefix) :].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="EMPTY_BEARER_TOKEN")
    return token


async def require_ops_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    token = _extract_bearer(authorization)
    payload = verify_access_token(token)
    username = str(payload.get("sub") or "").strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="INVALID_TOKEN_SUBJECT")
    user = user_store.USER_STORE.get_user(username)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="USER_NOT_FOUND_OR_DISABLED")
    roles = [str(r).strip() for r in (user.roles or []) if str(r).strip()]
    if not roles or not (set(roles) & CANONICAL_OPS_ROLES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "error": {"code": "INVALID_OR_EMPTY_ROLES", "message": "账号未分配有效运维角色"},
            },
        )
    return {"username": user.username, "roles": roles}


def _rbac_forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "success": False,
            "error": {"code": "RBAC_FORBIDDEN", "message": "当前角色无权执行此操作"},
        },
    )


async def require_read_ops(
    current_user: Annotated[dict, Depends(require_ops_user)],
) -> dict:
    """所有已登录且角色合法的运维用户可读（含 read_only_auditor）。"""
    return current_user


async def require_tenant_write(
    current_user: Annotated[dict, Depends(require_ops_user)],
) -> dict:
    """租户侧写操作：配额、重建索引、缓存失效等（super_admin / tenant_ops）。"""
    if not (set(current_user.get("roles") or []) & TENANT_WRITE_ROLES):
        raise _rbac_forbidden()
    return current_user


async def require_super_admin(current_user: Annotated[dict, Depends(require_ops_user)]) -> dict:
    if "super_admin" not in set(current_user.get("roles") or []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN")
    return current_user
