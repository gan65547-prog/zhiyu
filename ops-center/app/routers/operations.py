from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
import re

from app.auth.deps import require_super_admin, require_tenant_write
from app.services.business_gateway import BusinessGateway
from app.services.cache_service import READ_CACHE


router = APIRouter()


OP_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-:.]{5,127}$")


def _require_write_headers(op_id: str | None, operator: str | None) -> None:
    if not op_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {"code": "MISSING_X_OP_ID", "message": "缺少写操作幂等头 X-Op-Id"},
            },
        )
    if not operator:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {"code": "MISSING_X_OPERATOR", "message": "缺少操作人头 X-Operator"},
            },
        )
    if not OP_ID_PATTERN.match(op_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": {"code": "INVALID_X_OP_ID", "message": "X-Op-Id 格式非法"},
            },
        )


@router.post("/api/v1/operations/tenants/{tenant_id}/quota")
async def update_quota(
    tenant_id: str,
    body: dict,
    _current_user: Annotated[dict, Depends(require_tenant_write)],
    x_op_id: str | None = Header(default=None, alias="X-Op-Id"),
    x_operator: str | None = Header(default=None, alias="X-Operator"),
) -> dict:
    _require_write_headers(x_op_id, x_operator)
    gateway = BusinessGateway()
    return await gateway.request(
        "POST",
        f"/internal/admin/tenants/{tenant_id}/quota",
        json_body=body,
        op_id=x_op_id,
        operator=x_operator,
    )


@router.delete("/api/v1/operations/tenants/{tenant_id}")
async def delete_tenant(
    tenant_id: str,
    _current_user: Annotated[dict, Depends(require_super_admin)],
    x_op_id: str | None = Header(default=None, alias="X-Op-Id"),
    x_operator: str | None = Header(default=None, alias="X-Operator"),
) -> dict:
    """删除租户（软删除，仅 super_admin）。需业务侧 internal admin 已实现 DELETE /internal/admin/tenants/{id}。"""
    _require_write_headers(x_op_id, x_operator)
    gateway = BusinessGateway()
    result = await gateway.request(
        "DELETE",
        f"/internal/admin/tenants/{tenant_id}",
        op_id=x_op_id,
        operator=x_operator,
    )
    # 清除缓存，确保列表及时刷新
    READ_CACHE.invalidate_all()
    return result


@router.post("/api/v1/operations/cache/invalidate")
async def invalidate_ops_cache(
    body: dict,
    _current_user: Annotated[dict, Depends(require_tenant_write)],
    x_op_id: str | None = Header(default=None, alias="X-Op-Id"),
    x_operator: str | None = Header(default=None, alias="X-Operator"),
) -> dict:
    """代理业务侧 Redis 缓存失效，并清空运维中心本地只读缓存。"""
    _require_write_headers(x_op_id, x_operator)
    gateway = BusinessGateway()
    upstream: dict | None = None
    try:
        upstream = await gateway.request(
            "POST",
            "/internal/admin/cache/invalidate",
            json_body=body,
            op_id=x_op_id,
            operator=x_operator,
        )
    finally:
        cleared = READ_CACHE.invalidate_all()
        if isinstance(upstream, dict):
            meta = dict(upstream.get("meta") or {})
            meta["local_cache_entries_cleared"] = cleared
            upstream["meta"] = meta
    return upstream


@router.post("/api/v1/operations/documents/reindex")
async def reindex_documents(
    body: dict,
    _current_user: Annotated[dict, Depends(require_tenant_write)],
    x_op_id: str | None = Header(default=None, alias="X-Op-Id"),
    x_operator: str | None = Header(default=None, alias="X-Operator"),
) -> dict:
    _require_write_headers(x_op_id, x_operator)
    gateway = BusinessGateway()
    return await gateway.request(
        "POST",
        "/internal/admin/documents/reindex",
        json_body=body,
        op_id=x_op_id,
        operator=x_operator,
    )
