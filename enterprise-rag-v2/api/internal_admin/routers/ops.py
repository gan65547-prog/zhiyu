from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request, HTTPException

from api.deps import get_internal_admin_identity


router = APIRouter()


def _error(code: str, message: str, request_id: Optional[str], status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error": {"code": code, "message": message},
            "meta": {"request_id": request_id},
        },
    )


@router.get("/operations")
async def list_operations(
    request: Request,
    identity: Annotated[dict, Depends(get_internal_admin_identity)],
    tenant_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    db = request.app.state.db
    conditions = []
    params: dict[str, object] = {
        "limit": page_size,
        "offset": (page - 1) * page_size,
    }
    if tenant_id:
        conditions.append("tenant_id = :tenant_id")
        params["tenant_id"] = tenant_id
    if action:
        conditions.append("action = :action")
        params["action"] = action
    if status:
        conditions.append("status = :status")
        params["status"] = status
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = await db.fetch_all(
        f"""
        SELECT operation_id, tenant_id, action, status, operator_name, created_at, finished_at, error_message
        FROM ops_operations
        {where_sql}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """,
        params,
    )

    count_row = await db.fetch_one(
        f"""
        SELECT COUNT(*) AS total
        FROM ops_operations
        {where_sql}
        """,
        {k: v for k, v in params.items() if k not in {"limit", "offset"}},
    )

    total = int(dict(count_row).get("total", 0)) if count_row else 0
    total_pages = (total + page_size - 1) // page_size if page_size else 0

    return {
        "success": True,
        "message": "ok",
        "data": [dict(r) for r in rows],
        "meta": {
            "request_id": identity["request_id"],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


@router.get("/operations/{operation_id}")
async def get_operation_detail(
    operation_id: str,
    request: Request,
    identity: Annotated[dict, Depends(get_internal_admin_identity)],
):
    db = request.app.state.db
    row = await db.fetch_one(
        """
        SELECT *
        FROM ops_operations
        WHERE operation_id = :operation_id
        LIMIT 1
        """,
        {"operation_id": operation_id},
    )
    if not row:
        _error("OPERATION_NOT_FOUND", "操作记录不存在", identity["request_id"], 404)

    return {
        "success": True,
        "message": "ok",
        "data": dict(row),
        "meta": {"request_id": identity["request_id"]},
    }


@router.get("/operations/{operation_id}/tasks")
async def get_operation_tasks(
    operation_id: str,
    request: Request,
    identity: Annotated[dict, Depends(get_internal_admin_identity)],
):
    db = request.app.state.db
    rows = await db.fetch_all(
        """
        SELECT task_id, event_type, message, payload, retry_count, error_code, created_at
        FROM ops_task_events
        WHERE operation_id = :operation_id
        ORDER BY created_at ASC
        """,
        {"operation_id": operation_id},
    )
    return {
        "success": True,
        "message": "ok",
        "data": [dict(r) for r in rows],
        "meta": {"request_id": identity["request_id"], "operation_id": operation_id},
    }

