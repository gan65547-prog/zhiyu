"""
TenantRepository单元测试
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from infrastructure.repositories.tenant_repository import TenantRepositoryImpl
from infrastructure.database.models import Tenant, TenantStatus


class MockSession:
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
    def __init__(self, rowcount=1):
        self._rowcount = rowcount

    @property
    def rowcount(self):
        return self._rowcount

    def scalars(self):
        return MockScalars([])

    def scalar_one(self):
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


class TestTenantRepository:
    """TenantRepository测试"""

    @pytest.fixture
    def mock_session(self):
        return MockSession()

    @pytest.fixture
    def repo(self, mock_session):
        return TenantRepositoryImpl(mock_session)

    @pytest.fixture
    def sample_tenant_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_tenant(self, repo, mock_session):
        """测试创建租户"""
        tenant = Tenant(
            id=uuid4(),
            name="Test Tenant",
            contact_email="test@example.com",
            status=TenantStatus.ACTIVE
        )

        result = await repo.create(tenant)

        assert tenant in mock_session.added
        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo, sample_tenant_id):
        """测试根据ID获取"""
        result = await repo.get_by_id(sample_tenant_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_email(self, repo):
        """测试根据邮箱获取"""
        result = await repo.get_by_email("test@example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_tenant(self, repo, mock_session):
        """测试更新租户"""
        tenant = Tenant(
            id=uuid4(),
            name="Original",
            contact_email="test@example.com",
            status=TenantStatus.ACTIVE
        )

        result = await repo.update(tenant)

        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_delete_tenant(self, repo, mock_session, sample_tenant_id):
        """测试删除租户"""
        result = await repo.delete(sample_tenant_id)

        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_exists_tenant(self, repo, sample_tenant_id):
        """测试检查租户存在"""
        result = await repo.exists(sample_tenant_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_list_by_tenant(self, repo, sample_tenant_id):
        """测试根据租户ID列表查询"""
        result = await repo.list_by_tenant(sample_tenant_id)
        assert result.total == 0
        assert len(result.items) == 0
