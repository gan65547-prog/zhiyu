"""
日志中间件

提供请求日志记录功能
"""

import time
import uuid
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from infrastructure.logging.logger import set_log_context, clear_log_context, get_logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    def __init__(self, app):
        super().__init__(app)
        # 延迟初始化 logger，在第一次请求时获取
        self._logger = None

    def _get_logger(self):
        """延迟获取 logger"""
        if self._logger is None:
            self._logger = get_logger("api")
        return self._logger

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        request_id = str(uuid.uuid4())
        start_time = time.time()

        set_log_context(
            trace_id=request_id,
            user_id=request.headers.get("X-User-ID"),
            tenant_id=request.headers.get("X-Tenant-ID"),
        )

        self._get_logger().info(
            f"Request started: {request.method} {request.url.path}",
            __module__="api.middleware.logging",
            method=request.method,
            path=request.url.path,
            query=str(request.query_params),
            client_ip=self._get_client_ip(request)
        )

        try:
            response = await call_next(request)

            duration = time.time() - start_time

            self._get_logger().info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)",
                __module__="api.middleware.logging",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=int(duration * 1000)
            )

            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            duration = time.time() - start_time

            self._get_logger().error(
                f"Request failed: {request.method} {request.url.path} - {str(e)}",
                __module__="api.middleware.logging",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=int(duration * 1000)
            )
            raise

        finally:
            clear_log_context()

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"


class TenantContextMiddleware(BaseHTTPMiddleware):
    """租户上下文中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        tenant_id = request.headers.get("X-Tenant-ID")
        workspace_id = request.headers.get("X-Workspace-ID")
        user_id = request.headers.get("X-User-ID")

        if tenant_id or workspace_id or user_id:
            set_log_context(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                user_id=user_id
            )

        response = await call_next(request)

        if tenant_id or workspace_id or user_id:
            clear_log_context()

        return response
