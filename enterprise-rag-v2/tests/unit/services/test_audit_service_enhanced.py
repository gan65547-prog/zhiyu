"""
审计日志服务测试
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from services.audit.service import (
    AuditService,
    AuditAction,
    AuditLogCreate,
)
from infrastructure.database.models import AuditLog


@pytest.fixture
def mock_session():
    """模拟数据库会话"""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    
    # 修复: 正确配置execute的返回值
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=mock_result)
    
    return session


@pytest.fixture
def audit_service(mock_session):
    """创建审计服务实例"""
    return AuditService(mock_session)


class TestAuditService:
    """审计服务测试"""

    @pytest.mark.asyncio
    async def test_log_creates_entry(self, audit_service, mock_session):
        """测试创建审计日志"""
        user_id = uuid4()
        tenant_id = uuid4()

        result = await audit_service.log(
            action=AuditAction.LOGIN,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="user",
            resource_id=str(user_id),
            ip_address="127.0.0.1"
        )

        assert mock_session.add.called
        assert mock_session.flush.called

    @pytest.mark.asyncio
    async def test_log_login_success(self, audit_service, mock_session):
        """测试登录成功日志"""
        user_id = uuid4()
        tenant_id = uuid4()

        result = await audit_service.log_login(
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address="127.0.0.1",
            user_agent="TestAgent",
            success=True
        )

        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_log_login_failed(self, audit_service, mock_session):
        """测试登录失败日志"""
        result = await audit_service.log_login(
            user_id=None,
            tenant_id=None,
            ip_address="127.0.0.1",
            success=False,
            error_message="用户不存在",
            username="testuser"
        )

        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_log_logout(self, audit_service, mock_session):
        """测试登出日志"""
        user_id = uuid4()
        tenant_id = uuid4()

        result = await audit_service.log_logout(
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address="127.0.0.1"
        )

        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_log_data_change(self, audit_service, mock_session):
        """测试数据变更日志"""
        user_id = uuid4()
        tenant_id = uuid4()

        result = await audit_service.log_data_change(
            action=AuditAction.TENANT_UPDATE,
            resource_type="tenant",
            resource_id=str(tenant_id),
            user_id=user_id,
            tenant_id=tenant_id,
            old_value={"name": "old"},
            new_value={"name": "new"}
        )

        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_log_account_locked(self, audit_service, mock_session):
        """测试账户锁定日志"""
        user_id = uuid4()
        tenant_id = uuid4()

        result = await audit_service.log_account_locked(
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address="127.0.0.1",
            reason="too_many_failed_attempts"
        )

        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_log_security_alert(self, audit_service, mock_session):
        """测试安全告警日志"""
        result = await audit_service.log_security_alert(
            alert_type="brute_force_attempt",
            ip_address="127.0.0.1",
            details={"attempts": 10}
        )

        assert mock_session.add.called

    def test_compute_hash(self, audit_service):
        """测试哈希计算"""
        log_entry = AuditLog(
            id=uuid4(),
            action="login",
            created_at=datetime.utcnow(),
            tenant_id=uuid4(),
            user_id=uuid4(),
            resource_type="user",
            resource_id=str(uuid4()),
            details={}
        )

        hash1 = audit_service._compute_hash(log_entry, None)
        hash2 = audit_service._compute_hash(log_entry, "prev_hash")

        assert len(hash1) == 64
        assert hash1 != hash2


class TestAuditAction:
    """审计动作枚举测试"""

    def test_audit_action_values(self):
        """测试审计动作枚举值"""
        assert AuditAction.LOGIN.value == "login"
        assert AuditAction.LOGIN_FAILED.value == "login_failed"
        assert AuditAction.ACCOUNT_LOCKED.value == "account_locked"
        assert AuditAction.USER_CREATE.value == "user_create"
        assert AuditAction.TENANT_CREATE.value == "tenant_create"
        assert AuditAction.SECURITY_ALERT.value == "security_alert"
