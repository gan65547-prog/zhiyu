from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_internal_admin_identity
from api.internal_admin.request_env import resolve_target_env
from apps.commercialization.services.quota_override_service import QuotaOverrideService
from services.ops.operation_service import OperationService


router = APIRouter()


def _get_ops_service(request: Request) -> OperationService:
    return OperationService(request.app.state.db)


def _error(code: str, message: str, request_id: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error": {"code": code, "message": message},
            "meta": {"request_id": request_id},
        },
    )


@router.post("/tenants/{tenant_id}/quota")
async def update_quota(
    tenant_id: str,
    body: dict,
    request: Request,
    identity: Annotated[dict, Depends(get_internal_admin_identity)],
):
    dimension = body.get("quota_type")
    value = body.get("value")
    if dimension not in {
        "users", "documents", "storage_mb", "api_calls_monthly", "chat_messages_monthly", "workspaces",
        "research_runs_monthly", "research_sources_monthly", "research_output_tokens_monthly",
    }:
        _error("INVALID_QUOTA_TYPE", "无效的配额维度", identity["request_id"], 400)
    if not isinstance(value, int) or value < 0:
        _error("INVALID_QUOTA_VALUE", "配额值必须为非负整数", identity["request_id"], 400)

    ops = _get_ops_service(request)
    op_id = identity["operation_id"]
    await ops.create_pending_operation(
        operation_id=op_id,
        operator_name=identity["operator"],
        action="QUOTA_UPDATE",
        target_env=resolve_target_env(request),
        target_service="enterprise-rag-v2",
        tenant_id=tenant_id,
        request_payload=body,
        source_ip=identity["client_ip"],
        operator_id=body.get("operator_id"),
        resource_type="quota",
        resource_id=f"{tenant_id}:{dimension}",
    )
    try:
        quota_override_svc = QuotaOverrideService(request.app.state.db, request.app.state.quota_service.redis)
        result = await quota_override_svc.set_override(
            tenant_id=tenant_id,
            dimension=dimension,
            override_value=value,
            reason=body.get("reason", ""),
            created_by=body.get("operator_id"),
            expires_at=None,
        )
        await ops.mark_succeeded(op_id, after_snapshot=result)
        return {"success": True, "message": "quota updated", "data": result, "meta": {"operation_id": op_id}}
    except Exception as e:
        await ops.mark_failed(op_id, str(e))
        _error("QUOTA_UPDATE_FAILED", str(e), identity["request_id"], 400)


@router.get("/tenants/{tenant_id}/quota/overrides")
async def get_quota_overrides(
    tenant_id: str,
    request: Request,
    identity: Annotated[dict, Depends(get_internal_admin_identity)],
):
    rows = await request.app.state.db.fetch_all(
        """
        SELECT tenant_id, dimension, override_value, reason, expires_at, created_by, created_at, updated_at
        FROM quota_overrides
        WHERE tenant_id = :tenant_id
        ORDER BY updated_at DESC, created_at DESC
        """,
        {"tenant_id": tenant_id},
    )
    return {
        "success": True,
        "message": "ok",
        "data": [dict(row) for row in rows],
        "meta": {"request_id": identity["request_id"], "tenant_id": tenant_id},
    }
