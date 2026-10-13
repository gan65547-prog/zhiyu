from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Optional

from ..models import QuotaExceededError
from ..services.quota_service import QuotaService
from api.deps import get_current_active_user, require_tenant_admin

router = APIRouter(prefix="/api/v1/quotas", tags=["quotas"])


def get_quota_service(request: Request) -> QuotaService:
    """从app.state获取QuotaService实例"""
    svc = getattr(request.app.state, "quota_service", None)
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "SERVICE_UNAVAILABLE", "message": "配额服务未初始化，请确认应用已正常启动"},
        )
    return svc


@router.get("/usage")
async def get_usage_info(
    request: Request,
    current_user: dict = Depends(get_current_active_user),
):
    """
    获取配额使用详情

    返回：
    - usage: 各维度当前使用量
    - limits: 各维度上限
    - percentages: 使用百分比
    - warnings: 接近上限的维度列表
    """
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail={"error": "FORBIDDEN", "message": "用户未绑定租户"})
    svc = get_quota_service(request)

    info = await svc.get_usage_info(tenant_id)

    return info


@router.get("/check/{dimension}")
async def check_quota_dimension(
    dimension: str,
    request: Request,
    current_user: dict = Depends(get_current_active_user),
):
    """查询单个维度的配额状态"""
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail={"error": "FORBIDDEN", "message": "用户未绑定租户"})
    svc = get_quota_service(request)

    result = await svc.get_quota_for_dimension(tenant_id, dimension)

    return result


@router.post("/reset-test")
async def reset_test_quota(
    request: Request,
    _admin_check=Depends(require_tenant_admin),
    current_user: dict = Depends(get_current_active_user),
):
    """
    测试用：重置配额（仅开发环境）

    ⚠️ 生产环境应禁用此接口
    """
    from ..config import settings

    if not settings.debug:
        raise HTTPException(status_code=403, detail={
            "error": "FORBIDDEN",
            "message": "此接口仅限开发环境使用"
        })

    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=403, detail={"error": "FORBIDDEN", "message": "用户未绑定租户"})
    svc = get_quota_service(request)

    # 重置所有维度为0
    from ..config_quota import build_quota_key
    quota_key = build_quota_key(tenant_id)
    await svc.redis.delete(quota_key)

    return {
        "success": True,
        "message": f"配额已重置: tenant={tenant_id}"
    }
