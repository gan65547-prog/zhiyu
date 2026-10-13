from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.auth.deps import require_read_ops
from app.services.business_gateway import BusinessGateway


router = APIRouter()


@router.get("/api/v1/operations/tenants")
async def list_tenants(
    _current_user: Annotated[dict, Depends(require_read_ops)],
    status_filter: Optional[str] = Query(None, alias="status"),
    plan: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    gateway = BusinessGateway()
    return await gateway.request(
        "GET",
        "/internal/admin/tenants",
        query_params={
            "status": status_filter,
            "plan": plan,
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/api/v1/operations/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    _current_user: Annotated[dict, Depends(require_read_ops)],
) -> dict:
    gateway = BusinessGateway()
    return await gateway.request("GET", f"/internal/admin/tenants/{tenant_id}")


@router.get("/api/v1/operations/tenants/{tenant_id}/usage")
async def get_tenant_usage(
    tenant_id: str,
    _current_user: Annotated[dict, Depends(require_read_ops)],
) -> dict:
    gateway = BusinessGateway()
    return await gateway.request("GET", f"/internal/admin/tenants/{tenant_id}/usage")


@router.get("/api/v1/operations")
async def list_operations(
    _current_user: Annotated[dict, Depends(require_read_ops)],
    tenant_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    gateway = BusinessGateway()
    return await gateway.request(
        "GET",
        "/internal/admin/operations",
        query_params={
            "tenant_id": tenant_id,
            "action": action,
            "status": status_filter,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/api/v1/operations/{operation_id}")
async def get_operation_detail(
    operation_id: str,
    _current_user: Annotated[dict, Depends(require_read_ops)],
) -> dict:
    gateway = BusinessGateway()
    return await gateway.request("GET", f"/internal/admin/operations/{operation_id}")


@router.get("/api/v1/operations/{operation_id}/tasks")
async def get_operation_tasks(
    operation_id: str,
    _current_user: Annotated[dict, Depends(require_read_ops)],
) -> dict:
    gateway = BusinessGateway()
    return await gateway.request("GET", f"/internal/admin/operations/{operation_id}/tasks")


@router.get("/api/v1/operations/audit/logs")
async def list_audit_logs(
    _current_user: Annotated[dict, Depends(require_read_ops)],
    tenant_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    start_at: Optional[str] = Query(None),
    end_at: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict:
    gateway = BusinessGateway()
    return await gateway.request(
        "GET",
        "/internal/admin/audit/logs",
        query_params={
            "tenant_id": tenant_id,
            "action": action,
            "resource_type": resource_type,
            "status": status_filter,
            "start_at": start_at,
            "end_at": end_at,
            "page": page,
            "page_size": page_size,
        },
    )
