from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException, status
from fastapi import Request

from app.auth.deps import require_read_ops
from app.config import get_settings
from app.services.business_gateway import BusinessGateway


router = APIRouter()


@router.get("/health/live")
async def health_live() -> dict:
    return {"status": "alive"}


@router.get("/health/ready")
async def health_ready(request: Request) -> dict:
    settings = get_settings()
    upstream = await _probe_upstream()
    prewarm = getattr(request.app.state, "prewarm_status", {"ok": False})
    if upstream["status"] != "ok":
        upstream["prewarm"] = prewarm
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=upstream)
    return {
        "status": "ready",
        "service": settings.app_name,
        "env": settings.app_env,
        "upstream_status": upstream["upstream_status"],
        "prewarm": prewarm,
    }


@router.get("/api/v1/operations/health/upstream")
async def health_upstream(
    request: Request,
    _current_user: Annotated[dict, Depends(require_read_ops)],
) -> dict:
    upstream = await _probe_upstream()
    upstream["prewarm"] = getattr(request.app.state, "prewarm_status", {"ok": False})
    return upstream


async def _probe_upstream() -> dict:
    gateway = BusinessGateway()
    try:
        payload = await gateway.request("GET", "/health/live")
    except HTTPException as exc:
        code = exc.status_code
        health_state = "degraded"
        if code in {502, 503, 504}:
            health_state = "down"
        return {
            "status": health_state,
            "upstream_status": "unreachable",
            "upstream_status_code": code,
            "detail": exc.detail,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "down",
            "upstream_status": "error",
            "detail": str(exc),
        }

    return {
        "status": "ok",
        "upstream_status": "reachable",
        "upstream_payload": payload,
    }
