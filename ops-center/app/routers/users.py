from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.deps import require_read_ops, require_super_admin
from app.auth import user_store
from app.auth.user_store import OpsUser

router = APIRouter()


def _to_payload(user: OpsUser) -> dict:
    return {"id": user.id, "username": user.username, "is_active": user.is_active, "roles": user.roles}


@router.get("/api/v1/roles")
async def list_roles(_current_user: Annotated[dict, Depends(require_read_ops)]) -> dict:
    return {"success": True, "message": "ok", "data": user_store.USER_STORE.list_roles()}


@router.get("/api/v1/users")
async def list_users(_current_user: Annotated[dict, Depends(require_super_admin)]) -> dict:
    return {"success": True, "message": "ok", "data": [_to_payload(u) for u in user_store.USER_STORE.list_users()]}


@router.post("/api/v1/users")
async def create_user(body: dict, _current_user: Annotated[dict, Depends(require_super_admin)]) -> dict:
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    roles = [str(x).strip() for x in (body.get("roles") or []) if str(x).strip()]
    if not username or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_PAYLOAD")
    try:
        user = user_store.USER_STORE.create_user(username, password, roles or None)
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("INVALID_ROLE"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg) from exc
    return {"success": True, "message": "created", "data": _to_payload(user)}


@router.put("/api/v1/users/{username}")
async def update_user(username: str, body: dict, _current_user: Annotated[dict, Depends(require_super_admin)]) -> dict:
    try:
        user = user_store.USER_STORE.update_user(
            username,
            password=body.get("password"),
            is_active=body.get("is_active"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"success": True, "message": "updated", "data": _to_payload(user)}


@router.delete("/api/v1/users/{username}")
async def delete_user(username: str, _current_user: Annotated[dict, Depends(require_super_admin)]) -> dict:
    try:
        user_store.USER_STORE.delete_user(username)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"success": True, "message": "deleted", "data": {"username": username}}


@router.post("/api/v1/users/{username}/roles")
async def assign_roles(username: str, body: dict, _current_user: Annotated[dict, Depends(require_super_admin)]) -> dict:
    roles = [str(x).strip() for x in (body.get("roles") or []) if str(x).strip()]
    if not roles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="INVALID_ROLES")
    try:
        user = user_store.USER_STORE.assign_roles(username, roles)
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("INVALID_ROLE"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg) from exc
    return {"success": True, "message": "updated", "data": _to_payload(user)}
