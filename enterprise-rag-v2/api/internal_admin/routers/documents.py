from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_internal_admin_identity
from api.internal_admin.request_env import resolve_target_env
from infrastructure.queue.ops_tasks import ops_reindex_documents
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


@router.post("/documents/reindex")
async def dispatch_reindex(
    body: dict,
    request: Request,
    identity: Annotated[dict, Depends(get_internal_admin_identity)],
):
    tenant_id = body.get("tenant_id")
    if not tenant_id:
        _error("MISSING_TENANT_ID", "缺少 tenant_id", identity["request_id"], 400)

    ops = _get_ops_service(request)
    op_id = identity["operation_id"]
    await ops.create_pending_operation(
        operation_id=op_id,
        operator_name=identity["operator"],
        action="REINDEX_TRIGGER",
        target_env=resolve_target_env(request),
        target_service="enterprise-rag-v2",
        tenant_id=tenant_id,
        request_payload=body,
        source_ip=identity["client_ip"],
        operator_id=body.get("operator_id"),
        resource_type="document",
        resource_id=str(body.get("dataset_id") or ""),
    )
    try:
        await ops.mark_running(op_id)
        task_payload = dict(body)
        task_payload["operation_id"] = op_id
        async_result = ops_reindex_documents.apply_async(args=[task_payload], queue="documents_high")
        await ops.create_task_event(
            operation_id=op_id,
            task_id=async_result.id,
            event_type="DISPATCHED",
            message="reindex task dispatched",
            payload=task_payload,
        )
        return {
            "success": True,
            "message": "reindex task dispatched",
            "data": {"task_id": async_result.id},
            "meta": {"operation_id": op_id, "request_id": identity["request_id"]},
        }
    except Exception as e:
        await ops.mark_failed(op_id, str(e))
        _error("ASYNC_TASK_DISPATCH_FAILED", "异步任务派发失败", identity["request_id"], 500)
