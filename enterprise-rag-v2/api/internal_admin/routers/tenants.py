from typing import Annotated, Optional
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_internal_admin_identity, get_tenant_service
from core.value_objects.pagination import Pagination
from services.interfaces.tenant_service import TenantService


router = APIRouter()


@router.get("/tenants")
async def list_tenants(
    identity: Annotated[dict, Depends(get_internal_admin_identity)],
    tenant_service: Annotated[TenantService, Depends(get_tenant_service)],
    status_filter: Optional[str] = Query(None, alias="status"),
    plan: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = await tenant_service.list_tenants(
        status=status_filter,
        plan=plan,
        keyword=keyword,
        pagination=Pagination(page=page, page_size=page_size),
    )
    return {
        "success": True,
        "message": "ok",
        "data": result.items,
        "meta": {
            "request_id": identity["request_id"],
            "page": result.page,
            "page_size": result.page_size,
            "total": result.total,
            "data_source": "live",
            "snapshot_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: UUID,
    identity: Annotated[dict, Depends(get_internal_admin_identity)],
    tenant_service: Annotated[TenantService, Depends(get_tenant_service)],
):
    tenant = await tenant_service.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TENANT_NOT_FOUND")
    return {
        "success": True,
        "message": "ok",
        "data": tenant,
        "meta": {
            "request_id": identity["request_id"],
            "data_source": "live",
            "snapshot_at": datetime.now(timezone.utc).isoformat(),
        },
    }


@router.get("/tenants/{tenant_id}/usage")
async def get_tenant_usage(
    tenant_id: UUID,
    identity: Annotated[dict, Depends(get_internal_admin_identity)],
    tenant_service: Annotated[TenantService, Depends(get_tenant_service)],
):
    try:
        usage = await tenant_service.get_tenant_usage(tenant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TENANT_NOT_FOUND")

    return {
        "success": True,
        "message": "ok",
        "data": usage,
        "meta": {
            "request_id": identity["request_id"],
        },
    }


@router.delete("/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: UUID,
    identity: Annotated[dict, Depends(get_internal_admin_identity)],
    tenant_service: Annotated[TenantService, Depends(get_tenant_service)],
):
    """软删除租户（标记为已删除），供运维中心等业务网关调用。"""
    success = await tenant_service.delete_tenant(
        tenant_id,
        user_id=None,
        ip_address=identity.get("client_ip"),
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TENANT_NOT_FOUND")
    return {
        "success": True,
        "message": "tenant deleted",
        "data": {"tenant_id": str(tenant_id)},
        "meta": {"request_id": identity["request_id"]},
    }

