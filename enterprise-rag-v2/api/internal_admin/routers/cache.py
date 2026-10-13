from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.deps import get_internal_admin_identity
from apps.commercialization.services.quota_service import QuotaService
from services.ops.cache_invalidation import invalidate_ops_caches


router = APIRouter()


class CacheInvalidateBody(BaseModel):
    """缓存失效范围；默认仅清理 quota_overrides 相关 Redis 键。"""

    scopes: list[str] = Field(
        default_factory=lambda: ["quota_overrides"],
        description="quota_overrides | quota_counters | tenant_meta | all",
    )
    tenant_id: str | None = None
    dimension: str | None = Field(
        default=None,
        description="与 quota_overrides 联用，仅删除单维度覆盖缓存",
    )


def _error(code: str, message: str, request_id: str, status_code: int = 400) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error": {"code": code, "message": message},
            "meta": {"request_id": request_id},
        },
    )


_ALLOWED = frozenset(
    {"quota_overrides", "quota_counters", "tenant_meta", "all"}
)


@router.post("/cache/invalidate")
async def invalidate_cache(
    body: CacheInvalidateBody,
    request: Request,
    identity: Annotated[dict, Depends(get_internal_admin_identity)],
) -> dict[str, Any]:
    redis = getattr(request.app.state, "quota_service", None)
    redis = getattr(redis, "redis", None) if redis else None
    if redis is None:
        _error("REDIS_UNAVAILABLE", "Redis 未初始化，无法失效缓存", identity["request_id"], 503)

    for s in body.scopes:
        if s not in _ALLOWED:
            _error("INVALID_SCOPE", f"非法 scope: {s}", identity["request_id"], 400)

    if body.dimension and "quota_overrides" not in body.scopes and "all" not in body.scopes:
        _error("INVALID_BODY", "指定 dimension 时需包含 quota_overrides 或 all", identity["request_id"], 400)

    if body.dimension and body.dimension not in QuotaService.DIMENSIONS:
        _error("INVALID_DIMENSION", f"非法 dimension: {body.dimension}", identity["request_id"], 400)

    try:
        result = await invalidate_ops_caches(
            redis,
            scopes=body.scopes,
            tenant_id=body.tenant_id,
            dimension=body.dimension,
        )
    except Exception as e:
        _error("CACHE_INVALIDATE_FAILED", str(e), identity["request_id"], 500)

    return {
        "success": True,
        "message": "cache invalidated",
        "data": result,
        "meta": {"request_id": identity["request_id"]},
    }
