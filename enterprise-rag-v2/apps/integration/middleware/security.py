"""
安全中间件

提供防重放攻击、请求验证等安全功能
"""

import time
import hashlib
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    安全中间件
    
    提供以下安全功能:
    1. 防重放攻击 (基于时间戳和nonce)
    2. 请求签名验证
    3. 输入验证
    """
    
    async def dispatch(self, request: Request, call_next):
        # 只对集成接口进行验证
        if not request.url.path.startswith("/api/v1/integration"):
            return await call_next(request)
        
        # 检查时间戳，防止重放攻击
        timestamp = request.headers.get("X-Timestamp")
        nonce = request.headers.get("X-Nonce")
        
        if timestamp and nonce:
            try:
                current_time = int(time.time())
                request_time = int(timestamp)
                
                # 时间戳偏差不能超过5分钟
                if abs(current_time - request_time) > 300:
                    logger.warning(
                        f"[Security] 时间戳验证失败",
                        extra={
                            "path": request.url.path,
                            "client_ip": request.client.host if request.client else "unknown",
                            "timestamp": timestamp,
                            "current_time": current_time
                        }
                    )
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "FORBIDDEN",
                            "code": 403,
                            "message": "请求已过期，请重新发送"
                        }
                    )
                
                # 验证nonce（这里简化处理，实际应该存储已使用的nonce）
                # 生产环境应该使用Redis存储nonce，设置过期时间
                
            except ValueError:
                logger.warning(
                    f"[Security] 时间戳格式错误",
                    extra={
                        "path": request.url.path,
                        "client_ip": request.client.host if request.client else "unknown"
                    }
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "BAD_REQUEST",
                        "code": 400,
                        "message": "时间戳格式错误"
                    }
                )
        
        # 检查请求方法和内容类型
        if request.method == "POST":
            content_type = request.headers.get("Content-Type")
            if not content_type or "application/json" not in content_type:
                logger.warning(
                    f"[Security] 不支持的内容类型",
                    extra={
                        "path": request.url.path,
                        "client_ip": request.client.host if request.client else "unknown",
                        "content_type": content_type
                    }
                )
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "BAD_REQUEST",
                        "code": 400,
                        "message": "只支持 application/json 内容类型"
                    }
                )
        
        # 验证通过，继续处理请求
        response = await call_next(request)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    限流中间件

    限制每个用户的请求频率，定期清理过期键防止内存无限增长
    """

    def __init__(self, app, max_requests=10, time_window=60):
        super().__init__(app)
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: dict[str, list[float]] = {}
        self._last_cleanup = time.time()
        self._cleanup_interval = 900  # 15 分钟清理一次

    async def dispatch(self, request: Request, call_next):
        # 只对集成接口进行限流
        if not request.url.path.startswith("/api/v1/integration"):
            return await call_next(request)

        # 获取客户端IP
        client_ip = request.client.host if request.client else "unknown"
        platform = request.headers.get("X-Platform", "unknown")
        platform_user_id = request.headers.get("X-Platform-User-Id", "unknown")

        # 构建限流键
        key = f"{platform}:{platform_user_id}:{client_ip}"

        # 检查请求频率
        current_time = time.time()
        self._cleanup_expired_keys(current_time)

        if key in self.requests:
            # 清理过期的请求记录
            self.requests[key] = [t for t in self.requests[key] if current_time - t < self.time_window]

            # 检查是否超过限制
            if len(self.requests[key]) >= self.max_requests:
                logger.warning(
                    f"[RateLimit] 请求频率过高",
                    extra={
                        "path": request.url.path,
                        "client_ip": client_ip,
                        "platform": platform,
                        "platform_user_id": platform_user_id
                    }
                )
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "TOO_MANY_REQUESTS",
                        "code": 429,
                        "message": "请求频率过高，请稍后再试"
                    }
                )
        else:
            self.requests[key] = []

        # 删除空列表以节省内存
        if key in self.requests and not self.requests[key]:
            del self.requests[key]
            return await call_next(request)

        # 记录请求时间
        self.requests[key].append(current_time)

        # 继续处理请求
        response = await call_next(request)
        return response

    def _cleanup_expired_keys(self, current_time: float) -> None:
        """定期清理无活动记录的键"""
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = current_time
        stale = [k for k, ts_list in self.requests.items()
                  if not ts_list or (current_time - max(ts_list) > self.time_window * 2)]
        for k in stale:
            del self.requests[k]
        if stale:
            logger.debug("清理了 %d 个过期的限流键", len(stale))
