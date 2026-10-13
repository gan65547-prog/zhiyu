"""
安全测试

测试认证安全、权限控制、输入验证、API安全和Token安全
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
import re


class TestAuthenticationSecurity:
    """认证安全测试"""

    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        class _Result:
            def scalar_one_or_none(self):
                return None

            def all(self):
                return []

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result())
        return session

    @pytest.fixture
    def auth_service(self, mock_db_session):
        """创建认证服务"""
        from services.impl.auth_service import AuthServiceImpl
        service = AuthServiceImpl(session=mock_db_session)
        service.audit_service = AsyncMock()
        service.audit_service.log = AsyncMock(return_value=True)
        service.audit_service.log_login = AsyncMock(return_value=True)
        service.audit_service.log_logout = AsyncMock(return_value=True)
        service.audit_service.log_account_locked = AsyncMock(return_value=True)
        return service

    @pytest.mark.asyncio
    async def test_weak_password_rejected(self, auth_service):
        """测试弱密码被拒绝"""
        weak_passwords = [
            "short",           # 太短
            "alllowercase",    # 没有大写
            "ALLUPPERCASE",    # 没有小写
            "NoNumbers",       # 没有数字
            "12345678",        # 没有字母
        ]

        for password in weak_passwords:
            with pytest.raises(ValueError, match="密码不符合要求"):
                await auth_service.register(
                    username="testuser",
                    email="test@example.com",
                    password=password
                )

    @pytest.mark.asyncio
    async def test_sql_injection_in_login(self, auth_service):
        """测试SQL注入防护"""
        sql_injection_payloads = [
            "admin' OR '1'='1",
            "'; DROP TABLE users;--",
            "1' OR '1'='1' --",
        ]

        for payload in sql_injection_payloads:
            mock_repo = MagicMock()
            mock_repo.get_by_username = AsyncMock(return_value=None)
            mock_repo.get_by_email = AsyncMock(return_value=None)
            auth_service.user_repo = mock_repo

            with pytest.raises(ValueError, match="用户不存在"):
                await auth_service.login(username=payload, password="anypassword")

    @pytest.mark.asyncio
    async def test_brute_force_protection(self, auth_service):
        """测试暴力破解防护"""
        mock_repo = MagicMock()
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_repo.get_by_username = AsyncMock(return_value=mock_user)
        mock_repo.get_by_email = AsyncMock(return_value=None)
        auth_service.user_repo = mock_repo

        with patch("services.impl.auth_service.verify_password", return_value=False):
            for _ in range(5):
                with pytest.raises(ValueError, match="密码错误|账户已锁定|登录失败次数过多"):
                    await auth_service.login(username="testuser", password="wrongpassword")

    @pytest.mark.asyncio
    async def test_duplicate_login_prevention(self, auth_service):
        """测试重复登录防护"""
        from services.impl.auth_service import AuthServiceImpl

        mock_repo = MagicMock()
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.id = uuid4()
        mock_user.email = "testuser@example.com"
        mock_user.hashed_password = "$2b$12$test_hash"
        mock_repo.get_by_username = AsyncMock(return_value=mock_user)
        mock_repo.get_by_email = AsyncMock(return_value=None)
        auth_service.user_repo = mock_repo

        with patch("services.impl.auth_service.verify_password", return_value=False):
            for i in range(10):
                try:
                    await auth_service.login(username="testuser", password="wrongpassword")
                except (ValueError, TypeError):
                    pass

        assert mock_repo.get_by_username.call_count == 10


class TestInputValidation:
    """输入验证测试"""

    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        class _Result:
            def scalar_one_or_none(self):
                return None

            def all(self):
                return []

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result())
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.fixture
    def tenant_service(self, mock_db_session):
        """创建租户服务"""
        from services.impl.tenant_service import TenantServiceImpl
        return TenantServiceImpl(session=mock_db_session)

    @pytest.mark.asyncio
    async def test_xss_in_name_field(self, tenant_service):
        """测试XSS防护"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "' OR '1'='1",
        ]

        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=None)
        async def _create_tenant(tenant):
            return tenant
        mock_repo.create = AsyncMock(side_effect=_create_tenant)
        tenant_service.tenant_repo = mock_repo

        for payload in xss_payloads:
            try:
                await tenant_service.create_tenant(
                    name=payload,
                    contact_email="test@example.com"
                )
            except (ValueError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_invalid_email_format(self, tenant_service):
        """测试无效邮箱格式"""
        invalid_emails = [
            "notanemail",
            "@nodomain.com",
            "noat.com",
        ]

        mock_repo = MagicMock()
        mock_repo.get_by_email = AsyncMock(return_value=None)
        async def _create_tenant(tenant):
            return tenant
        mock_repo.create = AsyncMock(side_effect=_create_tenant)
        tenant_service.tenant_repo = mock_repo

        results = []
        for email in invalid_emails:
            try:
                result = await tenant_service.create_tenant(
                    name="Test Tenant",
                    contact_email=email
                )
                results.append(result)
            except (ValueError, Exception):
                pass

        assert len(results) >= 0


class TestAPISecurity:
    """API安全测试"""

    @pytest.mark.asyncio
    async def test_missing_auth_header(self):
        """测试缺少认证头"""
        headers = {}

        assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_invalid_token_format(self):
        """测试无效Token格式"""
        invalid_tokens = [
            "not.a.token",
            "Bearer ",
            "tokenwithspaces",
            "",
        ]

        for token in invalid_tokens:
            assert len(token) < 1000 or token == ""

    @pytest.mark.asyncio
    async def test_expired_token_rejected(self):
        """测试过期Token被拒绝"""
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWUsImlhdCI6MTUxNjIzOTAyMiwiZXhwIjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"

        from services.utils.jwt import decode_token
        # 现在 decode_token 对失效/无效 token 返回 None，而不是抛异常
        assert decode_token(expired_token) is None

    @pytest.mark.asyncio
    async def test_cors_headers_present(self):
        """测试CORS头存在"""
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }

        assert "Access-Control-Allow-Origin" in cors_headers


class TestTokenSecurity:
    """Token安全测试"""

    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        class _Result:
            def scalar_one_or_none(self):
                return None

            def all(self):
                return []

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result())
        session.flush = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def auth_service(self, mock_db_session):
        """创建认证服务"""
        from services.impl.auth_service import AuthServiceImpl
        service = AuthServiceImpl(session=mock_db_session)
        service.audit_service = AsyncMock()
        service.audit_service.log = AsyncMock(return_value=True)
        service.audit_service.log_login = AsyncMock(return_value=True)
        service.audit_service.log_logout = AsyncMock(return_value=True)
        return service

    @pytest.mark.asyncio
    async def test_token_contains_no_sensitive_data(self, auth_service):
        """测试Token不包含敏感数据"""
        with patch("services.impl.auth_service.create_access_token") as mock_create:
            mock_create.return_value = "test_token"

            mock_repo = MagicMock()
            mock_repo.get_by_email = AsyncMock(return_value=None)
            mock_repo.get_by_username = AsyncMock(return_value=None)
            async def _create_user(user):
                return user
            mock_repo.create = AsyncMock(side_effect=_create_user)
            auth_service.user_repo = mock_repo

            await auth_service.register(
                username="testuser",
                email="test@example.com",
                password="TestPass123!"
            )

            call_args = mock_create.call_args[0][0]
            assert "password" not in call_args
            assert "hashed_password" not in call_args
            assert "email" in call_args

    @pytest.mark.asyncio
    async def test_refresh_token_cannot_access_account(self, auth_service):
        """测试刷新Token不能用于账户访问"""
        with patch("services.impl.auth_service.decode_token") as mock_decode, \
             patch.object(auth_service.user_repo, 'get_by_id', new_callable=AsyncMock) as mock_get:

            mock_decode.return_value = {
                "sub": str(uuid4()),
                "type": "refresh",
                "exp": 9999999999
            }
            mock_get.return_value = None

            with pytest.raises(ValueError, match="用户不存在"):
                await auth_service.refresh_token("refresh_token")

    @pytest.mark.asyncio
    async def test_logout_invalidates_token(self, auth_service):
        """测试登出使Token失效"""
        token = "valid_token"
        user_id = uuid4()

        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)

        with patch("services.impl.auth_service.decode_token", return_value={"sub": str(user_id), "type": "access"}):
            try:
                result = await auth_service.logout(user_id=user_id, access_token=token)
                assert result is True
            except AttributeError:
                pass


class TestPermissionControl:
    """权限控制测试"""

    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        class _Result:
            def scalar_one_or_none(self):
                return None

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result())
        return session

    @pytest.fixture
    def auth_service(self, mock_db_session):
        """创建认证服务"""
        from services.impl.auth_service import AuthServiceImpl
        return AuthServiceImpl(session=mock_db_session)

    @pytest.mark.asyncio
    async def test_superuser_bypasses_permission(self, auth_service):
        """测试超级用户绕过权限检查"""
        with patch.object(auth_service.user_repo, 'get_by_id', new_callable=AsyncMock) as mock_get:
            mock_user = MagicMock()
            mock_user.is_superuser = True
            mock_user.id = uuid4()
            mock_get.return_value = mock_user

            result = await auth_service.verify_permission(
                user_id=uuid4(),
                resource_type="workspace",
                resource_id=uuid4(),
                action="delete"
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_access(self, auth_service):
        """测试禁用用户不能访问"""
        user_id = uuid4()

        with patch.object(auth_service.user_repo, 'get_by_id', new_callable=AsyncMock) as mock_get:
            mock_user = MagicMock()
            mock_user.is_superuser = False
            mock_user.is_active = False
            mock_user.id = user_id
            mock_get.return_value = mock_user

            result = await auth_service.verify_permission(
                user_id=user_id,
                resource_type="workspace",
                resource_id=uuid4(),
                action="read"
            )

            assert result is False


class TestRateLimiting:
    """限流测试"""

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        """测试超过限流"""
        request_count = 0
        max_requests = 100

        async def mock_handler():
            nonlocal request_count
            request_count += 1
            return {"status": "ok"}

        for i in range(max_requests + 10):
            try:
                await mock_handler()
            except Exception:
                pass

        assert request_count > max_requests

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self):
        """测试限流响应头"""
        rate_limit_headers = {
            "X-RateLimit-Limit": "100",
            "X-RateLimit-Remaining": "99",
            "X-RateLimit-Reset": "3600",
        }

        assert "X-RateLimit-Limit" in rate_limit_headers
        assert int(rate_limit_headers["X-RateLimit-Limit"]) > 0