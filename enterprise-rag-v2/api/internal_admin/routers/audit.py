from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request

from api.deps import get_internal_admin_identity


router = APIRouter()


@router.get("/audit/logs")
async def list_audit_logs(
    request: Request,
    identity: Annotated[dict, Depends(get_internal_admin_identity)],
    tenant_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    start_at: Optional[str] = Query(None, description="ISO8601 起始时间"),
    end_at: Optional[str] = Query(None, description="ISO8601 结束时间"),
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
    if resource_type:
        conditions.append("resource_type = :resource_type")
        params["resource_type"] = resource_type
    if status:
        conditions.append("status = :status")
        params["status"] = status
    if start_at:
        conditions.append("created_at >= :start_at")
        params["start_at"] = start_at
    if end_at:
        conditions.append("created_at <= :end_at")
        params["end_at"] = end_at

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = await db.fetch_all(
        f"""
        SELECT id, action, resource_type, resource_id, user_id, tenant_id, workspace_id,
               ip_address, user_agent, details, status, error_message, created_at
        FROM audit_logs
        {where_sql}
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
        """,
        params,
    )

    count_row = await db.fetch_one(
        f"""
        SELECT COUNT(*) AS total
        FROM audit_logs
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
