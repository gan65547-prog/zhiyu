"""AI 工作台数据中心 API。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_current_active_user, get_db, parse_tenant_uuid_from_user
from api.schemas.data_center import DataCenterResponse
from services.impl.data_center_service import DataCenterService


router = APIRouter()


def _user_id(current_user: dict) -> UUID:
    try:
        return UUID(str(current_user["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户身份无效") from exc


@router.get("/overview", response_model=DataCenterResponse)
async def data_center_overview(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    db=Depends(get_db),
):
    try:
        return await DataCenterService(db).overview(
            workspace_id=workspace_id,
            tenant_id=parse_tenant_uuid_from_user(current_user),
            user_id=_user_id(current_user),
            is_superuser=bool(current_user.get("is_superuser")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
