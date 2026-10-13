"""AI 工作台聚合能力 API。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_current_active_user, get_db, parse_tenant_uuid_from_user
from api.schemas.workbench import WorkbenchSearchResponse, WorkbenchTaskListResponse
from services.impl.workbench_service import WorkbenchService


router = APIRouter()


def _user_id(current_user: dict) -> UUID:
    try:
        return UUID(str(current_user["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效") from exc


@router.get("/search", response_model=WorkbenchSearchResponse)
async def search_workbench(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=50),
):
    try:
        return await WorkbenchService(db).search(
            query=q, workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), limit=limit,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get("/tasks", response_model=WorkbenchTaskListResponse)
async def list_workbench_tasks(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
    limit: int = Query(100, ge=1, le=200),
    include_history: bool = Query(False),
):
    try:
        return await WorkbenchService(db).list_tasks(
            workspace_id=workspace_id, tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user), is_superuser=bool(current_user.get("is_superuser")), limit=limit,
            include_history=include_history,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
