"""
按月统计已认证租户的 API 调用量，并支持管理员配置资源上限。
"""

from typing import Callable, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from services.utils.jwt import decode_token
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


def _extract_bearer_token(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    cookie = request.cookies.get("access_token")
    if cookie:
        return cookie
    return None


def _should_skip_quota(path: str) -> bool:
    if path in ("/health", "/metrics", "/favicon.ico"):
        return True
    if path.startswith("/api/docs") or path.startswith("/api/redoc") or path == "/api/openapi.json":
        return True
    if not path.startswith("/api/v1/"):
        return True
    # 认证与公开回调
    if path.startswith("/api/v1/auth/"):
        return True
    if path.startswith("/api/v1/webhooks/"):
        return True
    if path.startswith("/api/v1/integration/"):
        return True
    # 对话单独计 chat_messages_monthly
    if path.startswith("/api/v1/chat"):
        return True
    # 配额统计接口不计入业务 API
    if path.startswith("/api/v1/quotas"):
        return True
    return False


class MonthlyApiQuotaMiddleware(BaseHTTPMiddleware):
    """对已携带有效 JWT 的请求按租户计入 api_calls_monthly，超限时返回 403。"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if _should_skip_quota(path):
            return await call_next(request)

        token = _extract_bearer_token(request)
        if not token:
            return await call_next(request)

        payload = decode_token(token)
        if not payload or payload.get("type") == "refresh":
            return await call_next(request)

        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return await call_next(request)

        quota_svc = getattr(request.app.state, "quota_service", None)
        if not quota_svc:
            return await call_next(request)

        try:
            await quota_svc.check_and_increment(str(tenant_id), "api_calls_monthly", 1)
        except Exception as exc:
            # Redis 异常不应拖垮整个 API。
            logger.warning(
                "按月 API 配额计数失败，已跳过本次计数: tenant=%s error=%s",
                tenant_id,
                exc,
                exc_info=True,
            )

        return await call_next(request)
