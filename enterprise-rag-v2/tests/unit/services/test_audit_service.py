"""
审计日志服务测试
"""

import pytest
from uuid import uuid4
from unittest.mock import MagicMock
from datetime import datetime


class MockSession:
    """模拟数据库会话"""
    def __init__(self):
        self.added = []
        self.flushed = False
        self.refreshed = []

    def add(self, entity):
        self.added.append(entity)

    async def flush(self):
        self.flushed = True

    async def refresh(self, entity):
        self.refreshed.append(entity)

    async def execute(self, query):
        return MockResult()


class MockResult:
    def scalars(self):
        return MockScalars([])

    def scalar(self):
        return 0

    def scalar_one_or_none(self):
        return None


class MockScalars:
    def __init__(self, data):
        self._data = data

    def all(self):
        return self._data

    def one_or_none(self):
        return self._data[0] if self._data else None


class TestAuditService:
    """审计日志服务测试"""

    @pytest.fixture
    def mock_session(self):
        return MockSession()

    @pytest.fixture
    def audit_service(self, mock_session):
        from services.audit.service import AuditService
        return AuditService(mock_session)

    @pytest.mark.asyncio
    async def test_log_basic(self, audit_service, mock_session):
        """测试基本日志记录"""
        from services.audit.service import AuditAction

        result = await audit_service.log(
            action=AuditAction.LOGIN,
            user_id=uuid4(),
            tenant_id=uuid4()
        )

        assert len(mock_session.added) == 1
        assert mock_session.flushed is True
        assert result.action == AuditAction.LOGIN.value

    @pytest.mark.asyncio
    async def test_log_login_success(self, audit_service, mock_session):
        """测试登录成功日志"""
        user_id = uuid4()
        tenant_id = uuid4()

        result = await audit_service.log_login(
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            success=True
        )

        assert result.action == "login"
        assert result.status == "success"
        assert result.ip_address == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_log_login_failed(self, audit_service, mock_session):
        """测试登录失败日志"""
        user_id = uuid4()

        result = await audit_service.log_login(
            user_id=user_id,
            tenant_id=None,
            ip_address="192.168.1.1",
            success=False,
            error_message="密码错误"
        )

        assert result.action == "login_failed"
        assert result.status == "failed"
        assert result.error_message == "密码错误"

    @pytest.mark.asyncio
    async def test_log_logout(self, audit_service, mock_session):
        """测试登出日志"""
        user_id = uuid4()
        tenant_id = uuid4()

        result = await audit_service.log_logout(
            user_id=user_id,
            tenant_id=tenant_id,
            ip_address="192.168.1.1"
        )

        assert result.action == "logout"
        assert str(result.user_id) == str(user_id)

    @pytest.mark.asyncio
    async def test_log_data_change(self, audit_service, mock_session):
        """测试数据变更日志"""
        from services.audit.service import AuditAction

        user_id = uuid4()
        tenant_id = uuid4()
        resource_id = str(uuid4())

        result = await audit_service.log_data_change(
            action=AuditAction.USER_UPDATE,
            resource_type="user",
            resource_id=resource_id,
            user_id=user_id,
            tenant_id=tenant_id,
            old_value={"name": "old"},
            new_value={"name": "new"},
            ip_address="192.168.1.1"
        )

        assert result.action == AuditAction.USER_UPDATE.value
        assert result.resource_type == "user"
        assert result.resource_id == resource_id
        assert result.details["old_value"]["name"] == "old"
        assert result.details["new_value"]["name"] == "new"

    @pytest.mark.asyncio
    async def test_log_tenant_create(self, audit_service, mock_session):
        """测试租户创建日志"""
        from services.audit.service import AuditAction

        tenant_id = uuid4()
        user_id = uuid4()

        result = await audit_service.log(
            action=AuditAction.TENANT_CREATE,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type="tenant",
            resource_id=str(tenant_id),
            details={"name": "New Tenant"}
        )

        assert result.action == AuditAction.TENANT_CREATE.value
        assert str(result.tenant_id) == str(tenant_id)

    @pytest.mark.asyncio
    async def test_log_document_upload(self, audit_service, mock_session):
        """测试文档上传日志"""
        from services.audit.service import AuditAction

        document_id = uuid4()
        user_id = uuid4()

        result = await audit_service.log(
            action=AuditAction.DOCUMENT_UPLOAD,
            user_id=user_id,
            resource_type="document",
            resource_id=str(document_id),
            details={
                "file_name": "test.pdf",
                "file_size": 1024
            }
        )

        assert result.action == AuditAction.DOCUMENT_UPLOAD.value
        assert result.resource_type == "document"

    @pytest.mark.asyncio
    async def test_get_user_logs(self, audit_service):
        """测试获取用户日志"""
        user_id = uuid4()

        result = await audit_service.get_user_logs(user_id, limit=10)

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_tenant_logs(self, audit_service):
        """测试获取租户日志"""
        tenant_id = uuid4()

        result = await audit_service.get_tenant_logs(tenant_id, limit=10)

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_resource_logs(self, audit_service):
        """测试获取资源日志"""
        result = await audit_service.get_resource_logs(
            resource_type="document",
            resource_id=str(uuid4())
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_get_failed_login_attempts(self, audit_service):
        """测试获取失败登录次数"""
        result = await audit_service.get_failed_login_attempts(
            ip_address="192.168.1.1",
            minutes=15
        )

        assert result == 0


class TestAuditAction:
    """审计操作类型测试"""

    def test_audit_action_values(self):
        """测试审计操作类型值"""
        from services.audit.service import AuditAction

        assert AuditAction.LOGIN.value == "login"
        assert AuditAction.LOGOUT.value == "logout"
        assert AuditAction.LOGIN_FAILED.value == "login_failed"
        assert AuditAction.USER_CREATE.value == "user_create"
        assert AuditAction.TENANT_CREATE.value == "tenant_create"
        assert AuditAction.DOCUMENT_UPLOAD.value == "document_upload"

    def test_audit_action_count(self):
        """测试审计操作类型数量"""
        from services.audit.service import AuditAction

        actions = list(AuditAction)
        assert len(actions) >= 20


class TestAuditLogCreate:
    """审计日志创建模型测试"""

    def test_create_minimal(self):
        """测试最小化创建"""
        from services.audit.service import AuditLogCreate, AuditAction

        log = AuditLogCreate(action=AuditAction.LOGIN)

        assert log.action == AuditAction.LOGIN
        assert log.tenant_id is None
        assert log.user_id is None

    def test_create_full(self):
        """测试完整创建"""
        from services.audit.service import AuditLogCreate, AuditAction

        tenant_id = uuid4()
        user_id = uuid4()

        log = AuditLogCreate(
            tenant_id=tenant_id,
            user_id=user_id,
            action=AuditAction.LOGIN,
            resource_type="user",
            resource_id=str(user_id),
            details={"method": "password"},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            status="success"
        )

        assert log.tenant_id == tenant_id
        assert log.user_id == user_id
        assert log.action == AuditAction.LOGIN
        assert log.resource_type == "user"
        assert log.ip_address == "192.168.1.1"
