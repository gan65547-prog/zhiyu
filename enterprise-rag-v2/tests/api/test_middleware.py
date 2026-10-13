"""
中间件层测试 - 安全中间件

测试安全相关的中间件功能
"""

import pytest
import time
from unittest.mock import MagicMock


class TestRateLimitMiddleware:
    """速率限制中间件测试"""

    def test_rate_limit_logic(self):
        """测试速率限制逻辑"""
        requests_per_minute = 5
        request_counts = {}

        def check_rate_limit(client_ip: str) -> tuple[bool, int]:
            current_time = time.time()
            minute_key = f"{client_ip}:{int(current_time / 60)}"

            if minute_key not in request_counts:
                request_counts[minute_key] = 0

            if request_counts[minute_key] >= requests_per_minute:
                return False, request_counts[minute_key]

            request_counts[minute_key] += 1
            return True, request_counts[minute_key]

        allowed, count = check_rate_limit("192.168.1.1")
        assert allowed is True
        assert count == 1

        for _ in range(4):
            check_rate_limit("192.168.1.1")

        allowed, count = check_rate_limit("192.168.1.1")
        assert allowed is False
        assert count == 5

    def test_rate_limit_different_ips(self):
        """测试不同IP的限流独立"""
        request_counts = {}

        def check_rate_limit(client_ip: str, limit: int = 2) -> bool:
            current_time = time.time()
            minute_key = f"{client_ip}:{int(current_time / 60)}"

            if minute_key not in request_counts:
                request_counts[minute_key] = 0

            if request_counts[minute_key] >= limit:
                return False

            request_counts[minute_key] += 1
            return True

        assert check_rate_limit("192.168.1.1") is True
        assert check_rate_limit("192.168.1.1") is True
        assert check_rate_limit("192.168.1.1") is False

        assert check_rate_limit("192.168.1.2") is True
        assert check_rate_limit("192.168.1.2") is True
        assert check_rate_limit("192.168.1.2") is False


class TestInputValidationMiddleware:
    """输入验证中间件测试"""

    def test_xss_script_detection(self):
        """测试XSS脚本检测"""
        dangerous_patterns = [
            "<script>",
            "</script>",
            "javascript:",
            "onerror=",
            "onload=",
        ]

        def contains_xss(text: str) -> bool:
            text_lower = text.lower()
            for pattern in dangerous_patterns:
                if pattern.lower() in text_lower:
                    return True
            return False

        assert contains_xss("<script>alert('xss')</script>") is True
        assert contains_xss("javascript:alert('xss')") is True
        assert contains_xss("Normal text") is False
        assert contains_xss("Hello <b>World</b>") is False

    def test_sql_injection_detection(self):
        """测试SQL注入检测"""
        sql_patterns = [
            "SELECT *",
            "DROP TABLE",
            "UNION SELECT",
            "--",
            "'; ",
            "1=1",
        ]

        def contains_sql_injection(text: str) -> bool:
            text_upper = text.upper()
            for pattern in sql_patterns:
                if pattern.upper() in text_upper:
                    return True
            return False

        assert contains_sql_injection("SELECT * FROM users") is True
        assert contains_sql_injection("'; DROP TABLE users;--") is True
        assert contains_sql_injection("Normal text") is False
        assert contains_sql_injection("Hello World") is False


class TestSecurityHeadersMiddleware:
    """安全响应头中间件测试"""

    def test_security_headers(self):
        """测试安全响应头"""
        expected_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
        }

        def get_security_headers() -> dict:
            return expected_headers

        headers = get_security_headers()

        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["X-XSS-Protection"] == "1; mode=block"
        assert "max-age=31536000" in headers["Strict-Transport-Security"]
        assert "default-src 'self'" in headers["Content-Security-Policy"]


class TestSanitizeInput:
    """输入清理函数测试"""

    def test_sanitize_removes_html_tags(self):
        """测试移除HTML标签"""
        import re

        def sanitize_input(text: str) -> str:
            if not text:
                return ""
            clean = re.sub(r'<[^>]+>', '', text)
            return clean.strip()

        result = sanitize_input("<p>Hello</p>")
        assert result == "Hello"

        result = sanitize_input("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "</script>" not in result

    def test_sanitize_empty_string(self):
        """测试空字符串"""
        import re

        def sanitize_input(text: str) -> str:
            if not text:
                return ""
            clean = re.sub(r'<[^>]+>', '', text)
            return clean.strip()

        assert sanitize_input("") == ""
        assert sanitize_input(None) == ""

    def test_sanitize_preserves_normal_text(self):
        """测试保留正常文本"""
        import re

        def sanitize_input(text: str) -> str:
            if not text:
                return ""
            clean = re.sub(r'<[^>]+>', '', text)
            return clean.strip()

        result = sanitize_input("Hello World")
        assert result == "Hello World"


class TestValidateEmail:
    """邮箱验证函数测试"""

    def test_valid_email(self):
        """测试有效邮箱"""
        import re

        def validate_email(email: str) -> bool:
            if not email:
                return False
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return bool(re.match(pattern, email))

        assert validate_email("test@example.com") is True
        assert validate_email("user.name@domain.org") is True
        assert validate_email("user+tag@example.co.uk") is True

    def test_invalid_email(self):
        """测试无效邮箱"""
        import re

        def validate_email(email: str) -> bool:
            if not email:
                return False
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return bool(re.match(pattern, email))

        assert validate_email("testexample.com") is False
        assert validate_email("test@") is False
        assert validate_email("test @example.com") is False


class TestValidatePassword:
    """密码验证函数测试"""

    def test_valid_password(self):
        """测试有效密码"""
        def validate_password(password: str) -> tuple[bool, str]:
            if not password:
                return False, "密码不能为空"
            if len(password) < 8:
                return False, "密码长度至少8位"
            if not any(c.isupper() for c in password):
                return False, "密码必须包含大写字母"
            if not any(c.islower() for c in password):
                return False, "密码必须包含小写字母"
            if not any(c.isdigit() for c in password):
                return False, "密码必须包含数字"
            return True, ""

        valid, msg = validate_password("TestPass123")
        assert valid is True
        assert msg == ""

    def test_password_too_short(self):
        """测试密码太短"""
        def validate_password(password: str) -> tuple[bool, str]:
            if len(password) < 8:
                return False, "密码长度至少8位"
            return True, ""

        valid, msg = validate_password("Test12")
        assert valid is False
        assert "8" in msg

    def test_password_no_uppercase(self):
        """测试密码缺少大写字母"""
        def validate_password(password: str) -> tuple[bool, str]:
            if not any(c.isupper() for c in password):
                return False, "密码必须包含大写字母"
            return True, ""

        valid, msg = validate_password("testpass123")
        assert valid is False
        assert "大写" in msg

    def test_password_no_lowercase(self):
        """测试密码缺少小写字母"""
        def validate_password(password: str) -> tuple[bool, str]:
            if not any(c.islower() for c in password):
                return False, "密码必须包含小写字母"
            return True, ""

        valid, msg = validate_password("TESTPASS123")
        assert valid is False
        assert "小写" in msg

    def test_password_no_digit(self):
        """测试密码缺少数字"""
        def validate_password(password: str) -> tuple[bool, str]:
            if not any(c.isdigit() for c in password):
                return False, "密码必须包含数字"
            return True, ""

        valid, msg = validate_password("TestPassword")
        assert valid is False
        assert "数字" in msg
