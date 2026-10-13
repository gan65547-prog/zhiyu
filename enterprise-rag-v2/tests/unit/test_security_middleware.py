"""
安全中间件测试
"""

import pytest
from fastapi import FastAPI, Request, HTTPException
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from api.middleware.security import (
    RateLimitMiddleware,
    RegistrationRateLimitMiddleware,
    CSRFMiddleware,
    InputValidationMiddleware,
    SecurityHeadersMiddleware,
    XSSProtectionMiddleware,
    sanitize_input,
    sanitize_html,
    validate_email,
    validate_password,
    generate_secure_token,
)


@pytest.fixture
def app():
    """创建测试应用"""
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    @app.post("/api/auth/register")
    async def register():
        return {"status": "registered"}
    
    @app.post("/api/data")
    async def data_endpoint():
        return {"status": "created"}
    
    return app


class TestRateLimitMiddleware:
    """速率限制中间件测试"""

    def test_allows_requests_under_limit(self, app):
        """测试允许低于限制的请求"""
        app.add_middleware(RateLimitMiddleware, requests_per_minute=10)
        client = TestClient(app)
        
        response = client.get("/test")
        assert response.status_code == 200

    def test_rate_limit_headers(self, app):
        """测试速率限制响应头"""
        app.add_middleware(RateLimitMiddleware, requests_per_minute=10)
        client = TestClient(app)
        
        response = client.get("/test")
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers


class TestInputValidationMiddleware:
    """输入验证中间件测试"""

    def test_valid_json_accepted(self, app):
        """测试有效JSON被接受"""
        app.add_middleware(InputValidationMiddleware)
        client = TestClient(app)
        
        response = client.post("/api/data", json={"name": "test"})
        assert response.status_code == 200


class TestSecurityHeadersMiddleware:
    """安全响应头中间件测试"""

    def test_security_headers_added(self, app):
        """测试安全响应头被添加"""
        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app)
        
        response = client.get("/test")
        
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Strict-Transport-Security" not in response.headers
        assert "Content-Security-Policy" in response.headers

    def test_hsts_added_for_https(self, app):
        """HSTS 只应在 HTTPS 响应中发送，避免 HTTP 环境被浏览器升级。"""
        app.add_middleware(SecurityHeadersMiddleware)
        client = TestClient(app, base_url="https://testserver")

        response = client.get("/test")

        assert response.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"


class TestSanitizeInput:
    """输入清理测试"""

    def test_removes_html_tags(self):
        """测试移除HTML标签"""
        result = sanitize_input("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "alert" not in result

    def test_escapes_special_characters(self):
        """测试转义特殊字符"""
        result = sanitize_input("&\"'")
        assert "&amp;" in result
        assert "&quot;" in result
        assert "&#x27;" in result

    def test_empty_input(self):
        """测试空输入"""
        assert sanitize_input("") == ""
        assert sanitize_input(None) == ""


class TestSanitizeHtml:
    """HTML清理测试"""

    def test_removes_dangerous_tags(self):
        """测试移除危险标签"""
        result = sanitize_html("<script>alert('xss')</script><p>Hello</p>")
        assert "<script>" not in result
        assert "<p>" in result

    def test_removes_event_handlers(self):
        """测试移除事件处理器"""
        result = sanitize_html("<p onclick='alert(1)'>Hello</p>")
        assert "onclick" not in result

    def test_allows_safe_tags(self):
        """测试允许安全标签"""
        result = sanitize_html("<p><b>Bold</b> and <i>italic</i></p>")
        assert "<p>" in result
        assert "<b>" in result
        assert "<i>" in result


class TestValidateEmail:
    """邮箱验证测试"""

    def test_valid_email(self):
        """测试有效邮箱"""
        assert validate_email("test@example.com") is True
        assert validate_email("user.name@domain.org") is True

    def test_invalid_email(self):
        """测试无效邮箱"""
        assert validate_email("invalid") is False
        assert validate_email("test@") is False
        assert validate_email("@example.com") is False


class TestValidatePassword:
    """密码验证测试"""

    def test_valid_password(self):
        """测试有效密码"""
        valid, msg = validate_password("Password123!")
        assert valid is True

    def test_short_password(self):
        """测试过短密码"""
        valid, msg = validate_password("Pass1!")
        assert valid is False
        assert "8" in msg

    def test_missing_uppercase(self):
        """测试缺少大写字母"""
        valid, msg = validate_password("password123!")
        assert valid is False

    def test_missing_lowercase(self):
        """测试缺少小写字母"""
        valid, msg = validate_password("PASSWORD123!")
        assert valid is False

    def test_missing_digit(self):
        """测试缺少数字"""
        valid, msg = validate_password("Password!")
        assert valid is False


class TestGenerateSecureToken:
    """安全令牌生成测试"""

    def test_token_length(self):
        """测试令牌长度"""
        token = generate_secure_token(32)
        assert len(token) >= 32

    def test_token_uniqueness(self):
        """测试令牌唯一性"""
        token1 = generate_secure_token()
        token2 = generate_secure_token()
        assert token1 != token2

    def test_default_length(self):
        """测试默认长度"""
        token = generate_secure_token()
        assert len(token) >= 32
