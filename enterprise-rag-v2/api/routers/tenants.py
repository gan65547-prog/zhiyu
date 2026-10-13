"""
租户路由

处理租户管理相关的API端点
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from api.schemas.tenant import (
    TenantCreateRequest,
    TenantUpdateRequest,
    TenantQueryRequest,
    TenantInfo,
    TenantCreateResponse,
    TenantDetailResponse,
    TenantListResponse,
    TenantDeleteResponse,
)
from api.deps import get_tenant_service, get_current_active_user, get_current_superuser
from services.interfaces.tenant_service import TenantService
from core.value_objects.pagination import Pagination
from infrastructure.logging.logger import get_logger


router = APIRouter()
logger = get_logger(__name__)

def _normalize_tenant_payload(item: dict) -> dict:
    """兼容历史脏数据：metadata 为 None 时兜底为 {}，避免响应模型校验 500"""
    payload = dict(item or {})
    if payload.get("metadata") is None:
        payload["metadata"] = {}
    return payload


@router.post("/", response_model=TenantCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: TenantCreateRequest,
    tenant_service: Annotated[TenantService, Depends(get_tenant_service)],
    current_user: Annotated[dict, Depends(get_current_superuser)]  # 仅管理员可创建租户
):
    """创建租户（仅管理员）"""
    try:
        result = await tenant_service.create_tenant(
            name=request.name,
            contact_email=request.contact_email,
            contact_phone=request.contact_phone,
            plan="free",
            metadata=request.metadata,
            admin_username=request.admin_username,
            admin_email=request.admin_email,
            admin_password=request.admin_password
        )
        return TenantCreateResponse(
            success=True,
            message="Tenant created successfully",
            data=TenantInfo(**_normalize_tenant_payload(result))
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to create tenant: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create tenant")


@router.get("/{tenant_id}", response_model=TenantDetailResponse)
async def get_tenant(
    tenant_id: UUID,
    tenant_service: Annotated[TenantService, Depends(get_tenant_service)],
    current_user: Annotated[dict, Depends(get_current_superuser)]  # 仅管理员可查看租户
):
    """获取租户详情（仅管理员）"""
    result = await tenant_service.get_tenant(tenant_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return TenantDetailResponse(success=True, data=TenantInfo(**_normalize_tenant_payload(result)))


@router.put("/{tenant_id}", response_model=TenantDetailResponse)
async def update_tenant(
    tenant_id: UUID,
    request: TenantUpdateRequest,
    tenant_service: Annotated[TenantService, Depends(get_tenant_service)],
    current_user: Annotated[dict, Depends(get_current_superuser)]  # 仅管理员可更新租户
):
    """更新租户（仅管理员）"""
    try:
        update_data = request.model_dump(exclude_unset=True)
        if "plan" in update_data:
            raise HTTPException(status_code=400, detail="plan 是历史兼容字段，开源版不再修改计划档位")
        if update_data.get("status"):
            update_data["status"] = update_data["status"].value

        result = await tenant_service.update_tenant(tenant_id, **update_data)
        return TenantDetailResponse(success=True, data=TenantInfo(**_normalize_tenant_payload(result)))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to update tenant: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update tenant")


@router.delete("/{tenant_id}", response_model=TenantDeleteResponse)
async def delete_tenant(
    tenant_id: UUID,
    tenant_service: Annotated[TenantService, Depends(get_tenant_service)],
    current_user: Annotated[dict, Depends(get_current_superuser)]  # 仅管理员可删除租户
):
    """删除租户（仅管理员）"""
    success = await tenant_service.delete_tenant(tenant_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return TenantDeleteResponse(success=True, message="Tenant deleted successfully")


@router.get("/", response_model=TenantListResponse)
async def list_tenants(
    tenant_service: Annotated[TenantService, Depends(get_tenant_service)],
    current_user: Annotated[dict, Depends(get_current_superuser)],  # 仅管理员可查看租户列表
    status: str = None,
    keyword: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """查询租户列表（仅管理员）"""
    pagination = Pagination(page=page, page_size=page_size)
    result = await tenant_service.list_tenants(
        status=status,
        keyword=keyword,
        pagination=pagination
    )

    items = [TenantInfo(**_normalize_tenant_payload(item)) for item in result.items]
    return TenantListResponse(
        success=True,
        data=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next=result.has_next,
        has_prev=result.has_prev
    )


@router.get("/{tenant_id}/usage")
async def get_tenant_usage(
    tenant_id: UUID,
    tenant_service: Annotated[TenantService, Depends(get_tenant_service)],
    current_user: Annotated[dict, Depends(get_current_superuser)]  # 仅管理员可查看租户使用情况
):
    """获取租户使用情况（仅管理员）"""
    try:
        result = await tenant_service.get_tenant_usage(tenant_id)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to get tenant usage: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get tenant usage")
