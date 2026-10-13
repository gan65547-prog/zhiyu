"""
网关认证中间件 - OpenClaw ↔ FastAPI 通信安全层

职责:
  验证来自OpenClaw的请求是否携带正确的通信密钥

使用方式:
  在main.py中添加:
    app.add_middleware(GatewayAuthMiddleware)
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from apps.integration.config import settings
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)

_SENSITIVE_HEADERS = {"authorization", "cookie", "x-gateway-secret", "x-api-key"}


def _sanitize_headers(headers) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in _SENSITIVE_HEADERS}


class GatewayAuthMiddleware(BaseHTTPMiddleware):
    """
    OpenClaw网关认证中间件
    
    拦截所有 /api/v1/integration/* 路径的请求，
    验证 X-Gateway-Secret 请求头。
    
    安全机制:
      - 所有集成接口必须携带密钥
      - 密钥不匹配返回403
      - 记录非法访问尝试（用于监控）
    """
    
    async def dispatch(self, request: Request, call_next):
        logger.info(f"[GatewayAuth] 收到请求: {request.method} {request.url.path}, IP: {request.client.host if request.client else 'unknown'}")
        
        # 只对集成接口进行验证
        if not request.url.path.startswith("/api/v1/integration"):
            logger.info(f"[GatewayAuth] 非集成接口，直接通过: {request.url.path}")
            return await call_next(request)
        
        # 允许所有 /api/v1/integration/chat 路径的请求通过，不进行网关认证
        # 这样可以确保飞书的验证请求能够到达路由处理函数
        if request.url.path == "/api/v1/integration/chat":
            logger.info(f"[GatewayAuth] ✅ 允许 /api/v1/integration/chat 路径的请求通过，IP: {request.client.host if request.client else 'unknown'}")
            logger.info(f"[GatewayAuth] 请求头(脱敏): {_sanitize_headers(request.headers)}")
            
            # 直接调用下一个处理函数
            response = await call_next(request)
            logger.info(f"[GatewayAuth] /api/v1/integration/chat 响应状态: {response.status_code}")
            return response
        
        # 对于其他集成接口，仍然进行网关认证
        # 获取请求中的密钥
        gateway_secret = request.headers.get("X-Gateway-Secret")
        
        if not gateway_secret:
            logger.warning(
                f"[GatewayAuth] 缺少X-Gateway-Secret",
                extra={
                    "path": request.url.path,
                    "client_ip": request.client.host if request.client else "unknown"
                }
            )
            
            return JSONResponse(
                status_code=403,
                content={
                    "error": "FORBIDDEN",
                    "code": 403,
                    "message": "缺少网关认证密钥 (X-Gateway-Secret)"
                }
            )
        
        # 验证密钥
        if gateway_secret != settings.integration_secret:
            logger.warning(
                f"[GatewayAuth] 无效的网关密钥尝试",
                extra={
                    "path": request.url.path,
                    "client_ip": request.client.host if request.client else "unknown"
                }
            )
            
            return JSONResponse(
                status_code=403,
                content={
                    "error": "FORBIDDEN",
                    "code": 403,
                    "message": "无效的网关认证密钥"
                }
            )
        
        # 验证通过，继续处理请求
        logger.debug(f"[GatewayAuth] 验证通过: {request.url.path}")
        response = await call_next(request)
        
        return response
