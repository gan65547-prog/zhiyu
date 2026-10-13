"""
安全中间件

提供速率限制、输入验证、CSRF防护等安全功能
"""

import time
import secrets
import hashlib
import re
from typing import Optional, Callable, Dict, Set
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from starlette.requests import Request
from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp, Scope, Receive, Send
from pydantic import BaseModel

from core.config import get_settings
from infrastructure.cache.redis import RedisCache


settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    速率限制中间件（分布式）

    优先使用 Redis 滑动窗口实现，多 Worker 共享计数；
    Redis 不可用时自动降级到内存限流。
    """

    REDIS_KEY_PREFIX = "ratelimit:v2:"

    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute

        # 内存降级存储（Redis 不可用时使用）
        self._request_counts: Dict[str, list] = defaultdict(list)
        self._cleanup_interval = 3600
        self._last_cleanup = time.time()

        # Redis 客户端（延迟初始化）
        self._redis = None

    async def _get_redis(self):
        """延迟获取 Redis 缓存实例。"""
        if self._redis is None:
            from infrastructure.cache.redis import RedisCache
            self._redis = RedisCache()
        return self._redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        client_ip = self._get_client_ip(request)

        if not await self._check_rate_limit(client_ip):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests. Please try again later."},
            )

        response = await call_next(request)

        remaining = await self._get_remaining_requests(client_ip)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    async def _check_rate_limit(self, client_ip: str) -> bool:
        """检查速率限制，优先 Redis，失败降级到内存。"""
        try:
            redis_cache = await self._get_redis()
            client = await redis_cache._get_client()
            key = f"{self.REDIS_KEY_PREFIX}{client_ip}"
            now = time.time()
            window_start = now - 60

            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.expire(key, 120)
            results = await pipe.execute()

            count = results[1] if len(results) > 1 else 0
            if count >= self.requests_per_minute:
                return False

            await client.zadd(key, {str(now): now})
            await client.expire(key, 120)
            return True
        except Exception:
            return self._check_rate_limit_memory(client_ip)

    def _check_rate_limit_memory(self, client_ip: str) -> bool:
        """内存降级限流"""
        now = time.time()
        self._cleanup_if_needed(now)
        minute_ago = now - 60

        self._request_counts[client_ip] = [
            t for t in self._request_counts[client_ip] if t > minute_ago
        ]

        if len(self._request_counts[client_ip]) >= self.requests_per_minute:
            return False

        self._request_counts[client_ip].append(now)
        return True

    async def _get_remaining_requests(self, client_ip: str) -> int:
        """获取剩余请求数"""
        try:
            redis_cache = await self._get_redis()
            client = await redis_cache._get_client()
            key = f"{self.REDIS_KEY_PREFIX}{client_ip}"
            window_start = time.time() - 60

            await client.zremrangebyscore(key, 0, window_start)
            count = await client.zcard(key)
            return max(0, self.requests_per_minute - count)
        except Exception:
            return self._get_remaining_requests_memory(client_ip)

    def _get_remaining_requests_memory(self, client_ip: str) -> int:
        """内存模式获取剩余请求数"""
        now = time.time()
        minute_ago = now - 60
        recent_requests = [
            t for t in self._request_counts[client_ip] if t > minute_ago
        ]
        return max(0, self.requests_per_minute - len(recent_requests))

    def _cleanup_if_needed(self, current_time: float) -> None:
        """清理过期记录（仅内存降级模式）"""
        if current_time - self._last_cleanup > self._cleanup_interval:
            minute_ago = current_time - 60
            for ip in list(self._request_counts.keys()):
                self._request_counts[ip] = [
                    t for t in self._request_counts[ip] if t > minute_ago
                ]
                if not self._request_counts[ip]:
                    del self._request_counts[ip]
            self._last_cleanup = current_time


class RegistrationRateLimitMiddleware(BaseHTTPMiddleware):
    """注册限流中间件 - 同IP 1分钟内最多3次注册"""

    REGISTER_PATHS = [
        "/api/v1/auth/register",
        "/api/auth/register",
        "/auth/register",
    ]
    MAX_ATTEMPTS = 3
    WINDOW_SECONDS = 60

    def __init__(self, app):
        super().__init__(app)
        self._cache: Optional[RedisCache] = None

    async def _get_cache(self):
        """复用全局 RedisCache 单例，避免创建独立连接池"""
        if self._cache is None:
            from infrastructure.cache.redis import get_cache as _get_singleton_cache
            self._cache = await _get_singleton_cache()
        return self._cache

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        if request.method == "POST" and request.url.path in self.REGISTER_PATHS:
            client_ip = self._get_client_ip(request)

            cache = await self._get_cache()
            key = f"register_rate_limit:{client_ip}"
            attempts = await cache.get(key)
            count = (attempts or 0) + 1

            if count > self.MAX_ATTEMPTS:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": f"注册请求过于频繁，请 {self.WINDOW_SECONDS} 秒后再试"}
                )

            await cache.set(key, count, ttl=self.WINDOW_SECONDS)

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF防护中间件 — 使用 Double Submit Cookie 模式"""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
    EXEMPT_PATHS = {
        "/health",
        "/health/live",
        "/health/ready",
        "/metrics",
        "/metrics/prometheus",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
    }
    CSRF_COOKIE_NAME = "csrf_token"
    CSRF_HEADER_NAME = "X-CSRF-Token"

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self._cache: Optional[RedisCache] = None

    async def _get_cache(self):
        """复用全局 RedisCache 单例，避免创建独立连接池"""
        if self._cache is None:
            from infrastructure.cache.redis import get_cache as _get_singleton_cache
            self._cache = await _get_singleton_cache()
        return self._cache

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        if not self.enabled:
            return await call_next(request)

        # 豁免路径（健康检查、指标等系统端点）
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)

        # 安全方法（GET/HEAD/OPTIONS/TRACE）：生成并下发 Token（Cookie + Header）
        if request.method in self.SAFE_METHODS:
            response = await call_next(request)
            csrf_token = await self._generate_or_get_token(request)
            response.headers[self.CSRF_HEADER_NAME] = csrf_token
            response.set_cookie(
                key=self.CSRF_COOKIE_NAME,
                value=csrf_token,
                httponly=False,        # 前端 JS 需读取以附加到请求头
                samesite="lax",
                secure=False,          # 生产环境应设为 True（需 HTTPS）
                max_age=3600,
            )
            return response

        # 非安全方法（POST/PUT/PATCH/DELETE）：校验 Token
        header_token = request.headers.get(self.CSRF_HEADER_NAME, "")
        cookie_token = request.cookies.get(self.CSRF_COOKIE_NAME, "")
        if not header_token or not cookie_token or header_token != cookie_token:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "CSRF token mismatch or missing"},
            )

        return await call_next(request)

    async def _generate_or_get_token(self, request: Request) -> str:
        """生成或获取CSRF Token（Redis 缓存，兼容多实例）"""
        session_id = request.cookies.get("session_id") or self._get_client_ip(request)
        cache_key = f"csrf_token:{session_id}"

        cache = await self._get_cache()
        existing_token = await cache.get(cache_key)
        if existing_token:
            return existing_token

        token = secrets.token_urlsafe(32)
        await cache.set(cache_key, token, ttl=3600)
        return token

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端IP"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


class JsonBodySecurityMiddleware:
    """
    JSON 请求体验证：合并原 InputValidation 与 XSSProtection 规则。

    使用纯 ASGI 实现：完整读取 body 并校验后，向下游注入重放的 receive。
    继承 BaseHTTPMiddleware 并在其中 await body 会破坏下游对 body 的读取；
    即便用 Request 重放，也可能触发 Starlette 对 StreamingResponse 的 Content-Length 问题。
    """

    SENSITIVE_PATTERNS = [
        (r"<script[^>]*>", "HTML script tags are not allowed"),
        (r"javascript:", "JavaScript protocol is not allowed"),
        (r"on\w+\s*=", "Inline event handlers are not allowed"),
        (r"<!--", "HTML comment start is not allowed"),
        (r"-->", "HTML comment end is not allowed"),
        (r"<iframe[^>]*>", "iframe tags are not allowed"),
        (r"<object[^>]*>", "object tags are not allowed"),
        (r"<embed[^>]*>", "embed tags are not allowed"),
        (r"<form[^>]*>", "form tags are not allowed"),
    ]

    SQL_INJECTION_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bUPDATE\b.*\bSET\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bEXEC\b|\bEXECUTE\b)",
        r"(--\s*$)",
        r"(;\s*--)",
    ]

    DANGEROUS_TAGS = [
        "<script", "</script", "<iframe", "</iframe",
        "<object", "</object", "<embed", "</embed",
        "<form", "</form", "javascript:", "vbscript:",
        "onload=", "onerror=", "onclick=", "onmouseover=",
        "onfocus=", "onblur=", "onsubmit=", "<svg", "</svg",
    ]

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        if method not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        content_type = headers.get("content-type", "")
        if "application/json" not in content_type.lower():
            await self.app(scope, receive, send)
            return

        body = b""
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                more = message.get("more_body", False)
            elif message["type"] == "http.disconnect":
                return

        async def disconnect_only_receive() -> dict:
            return {"type": "http.request", "body": b"", "more_body": False}

        try:
            text = body.decode("utf-8") if body else ""
        except UnicodeDecodeError:
            await JSONResponse(
                {"detail": "Invalid UTF-8 in request body"},
                status_code=status.HTTP_400_BAD_REQUEST,
            )(scope, disconnect_only_receive, send)
            return

        if body:
            lowered = text.lower()
            for dangerous in self.DANGEROUS_TAGS:
                if dangerous in lowered:
                    await JSONResponse(
                        {"detail": f"Potentially dangerous content detected: {dangerous}"},
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )(scope, disconnect_only_receive, send)
                    return

            for pattern, message in self.SENSITIVE_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    await JSONResponse(
                        {"detail": f"Invalid input: {message}"},
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )(scope, disconnect_only_receive, send)
                    return

            for pattern in self.SQL_INJECTION_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    await JSONResponse(
                        {"detail": "Invalid input: Potentially dangerous SQL pattern detected"},
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )(scope, disconnect_only_receive, send)
                    return

        sent = False

        async def replay_receive() -> dict:
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay_receive, send)


InputValidationMiddleware = JsonBodySecurityMiddleware
XSSProtectionMiddleware = JsonBodySecurityMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全响应头中间件"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Only send HSTS when the request itself is HTTPS. Sending this header
        # from the HTTP-only single-host deployment makes browsers remember an
        # HTTPS upgrade for an explicitly configured internal upstream without a TLS listener.
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https://cube.elemecdn.com https://shadow.elemecdn.com; connect-src 'self'; font-src 'self' data:"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response


def sanitize_input(text: str) -> str:
    """清理输入文本"""
    if not text:
        return ""

    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]*>", "", text)

    html_entities = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '/': '&#x2F;',
    }
    
    for char, entity in html_entities.items():
        text = text.replace(char, entity)

    return text.strip()


def sanitize_html(text: str) -> str:
    """清理HTML内容，保留安全标签"""
    if not text:
        return ""

    allowed_tags = ['p', 'br', 'b', 'i', 'u', 'strong', 'em', 'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
    
    text = re.sub(r'<(?!/?(' + '|'.join(allowed_tags) + r')\b)[^>]*>', '', text, flags=re.IGNORECASE)
    
    text = re.sub(r'on\w+\s*=', 'data-blocked=', text, flags=re.IGNORECASE)
    text = re.sub(r'javascript:', 'blocked:', text, flags=re.IGNORECASE)

    return text.strip()


def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password(password: str) -> tuple:
    """验证密码强度"""
    if len(password) < 8:
        return False, "密码长度至少8个字符"

    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)

    if not (has_upper and has_lower and has_digit):
        return False, "密码必须包含大小写字母和数字"

    if not has_special:
        return False, "密码建议包含特殊字符"

    return True, ""


def hash_api_key(key: str) -> str:
    """哈希API密钥"""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_secure_token(length: int = 32) -> str:
    """生成安全随机令牌"""
    return secrets.token_urlsafe(length)
