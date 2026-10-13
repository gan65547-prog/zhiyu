"""
登录失败锁定机制测试
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from services.impl.auth_service import AuthServiceImpl
from core.config import get_settings


settings = get_settings()


@pytest.fixture
def mock_session():
    """模拟数据库会话"""
    session = MagicMock()
    res = MagicMock()
    res.all.return_value = []
    res.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=res)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_cache():
    """模拟缓存"""
    cache = AsyncMock()
    cache.get = AsyncMock()
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    cache.exists = AsyncMock()
    return cache


@pytest.fixture
def auth_service(mock_session):
    """创建认证服务实例"""
    svc = AuthServiceImpl(mock_session)
    svc._check_is_tenant_admin = AsyncMock(return_value=False)
    return svc


class TestLoginLockout:
    """登录锁定测试"""

    @pytest.mark.asyncio
    async def test_account_lockout_after_max_attempts(self, auth_service, mock_session, mock_cache):
        """测试超过最大尝试次数后锁定账户"""
        user_id = uuid4()
        tenant_id = uuid4()
        
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.tenant_id = tenant_id
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.hashed_password = "hashed_password"
        mock_user.is_active = True
        mock_user.is_superuser = False
        
        mock_cache.exists.return_value = False
        mock_cache.get.return_value = settings.security.login_max_attempts - 1
        
        with patch.object(auth_service, 'cache', mock_cache):
            with patch.object(auth_service.user_repo, 'get_by_username', AsyncMock(return_value=mock_user)):
                with patch('services.impl.auth_service.verify_password', return_value=False):
                    with pytest.raises(ValueError) as exc_info:
                        await auth_service.login(
                            username="testuser",
                            password="wrongpassword",
                            ip_address="127.0.0.1"
                        )
                    
                    assert "锁定" in str(exc_info.value) or "locked" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_locked_account_cannot_login(self, auth_service, mock_session, mock_cache):
        """测试被锁定的账户无法登录"""
        user_id = uuid4()
        tenant_id = uuid4()
        
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.tenant_id = tenant_id
        mock_user.username = "testuser"
        mock_user.is_active = True
        
        mock_cache.exists.return_value = True
        
        with patch.object(auth_service, 'cache', mock_cache):
            with patch.object(auth_service.user_repo, 'get_by_username', AsyncMock(return_value=mock_user)):
                with pytest.raises(ValueError) as exc_info:
                    await auth_service.login(
                        username="testuser",
                        password="anypassword",
                        ip_address="127.0.0.1"
                    )
                
                assert "锁定" in str(exc_info.value) or "locked" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_successful_login_clears_attempts(self, auth_service, mock_session, mock_cache):
        """测试成功登录清除失败尝试记录"""
        user_id = uuid4()
        tenant_id = uuid4()
        
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.tenant_id = tenant_id
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.hashed_password = "hashed_password"
        mock_user.is_active = True
        mock_user.is_superuser = False
        
        mock_cache.exists.return_value = False
        
        with patch.object(auth_service, 'cache', mock_cache):
            with patch.object(auth_service.user_repo, 'get_by_username', AsyncMock(return_value=mock_user)):
                with patch('services.impl.auth_service.verify_password', return_value=True):
                    result = await auth_service.login(
                        username="testuser",
                        password="correctpassword",
                        ip_address="127.0.0.1"
                    )
                    
                    assert "user" in result
                    assert "access_token" in result
                    mock_cache.delete.assert_called()

    @pytest.mark.asyncio
    async def test_failed_login_records_attempt(self, auth_service, mock_session, mock_cache):
        """测试失败登录记录尝试次数"""
        mock_cache.exists.return_value = False
        mock_cache.get.return_value = 0
        
        with patch.object(auth_service, 'cache', mock_cache):
            with patch.object(auth_service.user_repo, 'get_by_username', AsyncMock(return_value=None)), \
                 patch.object(auth_service.user_repo, 'get_by_email', AsyncMock(return_value=None)):
                with pytest.raises(ValueError):
                    await auth_service.login(
                        username="nonexistent",
                        password="wrongpassword",
                        ip_address="127.0.0.1"
                    )
                
                mock_cache.set.assert_called()

    def test_lockout_settings(self):
        """测试锁定配置"""
        assert settings.security.login_max_attempts == 5
        assert settings.security.login_lockout_minutes == 15


class TestAccountLockoutHelpers:
    """账户锁定辅助方法测试"""

    @pytest.mark.asyncio
    async def test_is_account_locked(self, auth_service, mock_cache):
        """测试检查账户是否锁定"""
        user_id = uuid4()
        
        mock_cache.exists.return_value = True
        with patch.object(auth_service, 'cache', mock_cache):
            result = await auth_service._is_account_locked(user_id)
            assert result is True
        
        mock_cache.exists.return_value = False
        with patch.object(auth_service, 'cache', mock_cache):
            result = await auth_service._is_account_locked(user_id)
            assert result is False

    @pytest.mark.asyncio
    async def test_lock_account(self, auth_service, mock_cache):
        """测试锁定账户"""
        user_id = uuid4()
        
        with patch.object(auth_service, 'cache', mock_cache):
            await auth_service._lock_account(user_id, minutes=15)
            mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_unlock_account(self, auth_service, mock_cache):
        """测试解锁账户"""
        user_id = uuid4()
        
        with patch.object(auth_service, 'cache', mock_cache):
            await auth_service._unlock_account(user_id)
            mock_cache.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_failed_attempt(self, auth_service, mock_cache):
        """测试记录失败尝试"""
        mock_cache.get.return_value = 2
        
        with patch.object(auth_service, 'cache', mock_cache):
            count = await auth_service._record_failed_attempt("127.0.0.1")
            assert count == 3

    @pytest.mark.asyncio
    async def test_clear_failed_attempts(self, auth_service, mock_cache):
        """测试清除失败尝试记录"""
        with patch.object(auth_service, 'cache', mock_cache):
            await auth_service._clear_failed_attempts("127.0.0.1")
            mock_cache.delete.assert_called_once()


class TestAuditIntegration:
    """审计日志集成测试"""

    @pytest.mark.asyncio
    async def test_login_creates_audit_log(self, auth_service, mock_session):
        """测试登录创建审计日志"""
        user_id = uuid4()
        tenant_id = uuid4()
        
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.tenant_id = tenant_id
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.hashed_password = "hashed_password"
        mock_user.is_active = True
        mock_user.is_superuser = False
        
        mock_cache = AsyncMock()
        mock_cache.exists.return_value = False
        
        with patch.object(auth_service, 'cache', mock_cache):
            with patch.object(auth_service.user_repo, 'get_by_username', AsyncMock(return_value=mock_user)):
                with patch('services.impl.auth_service.verify_password', return_value=True):
                    result = await auth_service.login(
                        username="testuser",
                        password="correctpassword",
                        ip_address="127.0.0.1",
                        user_agent="TestAgent"
                    )
                    
                    assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_failed_login_creates_audit_log(self, auth_service, mock_session):
        """测试失败登录创建审计日志"""
        mock_cache = AsyncMock()
        mock_cache.exists.return_value = False
        mock_cache.get.return_value = 0
        
        with patch.object(auth_service, 'cache', mock_cache):
            with patch.object(auth_service.user_repo, 'get_by_username', AsyncMock(return_value=None)), \
                 patch.object(auth_service.user_repo, 'get_by_email', AsyncMock(return_value=None)):
                with pytest.raises(ValueError):
                    await auth_service.login(
                        username="nonexistent",
                        password="wrongpassword",
                        ip_address="127.0.0.1"
                    )
                
                assert mock_session.add.called
