"""
WorkspaceRepository单元测试
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from infrastructure.repositories.workspace_repository import (
    WorkspaceRepositoryImpl,
    WorkspaceMemberRepositoryImpl
)
from infrastructure.database.models import Workspace, WorkspaceMember, WorkspaceRole


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


class TestWorkspaceRepository:
    """WorkspaceRepository测试"""

    @pytest.fixture
    def mock_session(self):
        return MockSession()

    @pytest.fixture
    def repo(self, mock_session):
        return WorkspaceRepositoryImpl(mock_session)

    @pytest.fixture
    def sample_ws_id(self):
        return uuid4()

    @pytest.fixture
    def sample_tenant_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_workspace(self, repo, mock_session):
        """测试创建工作空间"""
        ws = Workspace(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Test Workspace",
            description="Test",
            metadata={}
        )

        result = await repo.create(ws)

        assert ws in mock_session.added
        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo, sample_ws_id):
        """测试根据ID获取"""
        result = await repo.get_by_id(sample_ws_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_workspace(self, repo, mock_session):
        """测试更新工作空间"""
        ws = Workspace(
            id=uuid4(),
            tenant_id=uuid4(),
            name="Original",
            description="Test",
            metadata={}
        )

        result = await repo.update(ws)

        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_delete_workspace(self, repo, mock_session, sample_ws_id):
        """测试删除工作空间"""
        result = await repo.delete(sample_ws_id)

        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_exists_workspace(self, repo, sample_ws_id):
        """测试检查工作空间存在"""
        result = await repo.exists(sample_ws_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_list_by_tenant(self, repo, sample_tenant_id):
        """测试根据租户ID列表"""
        result = await repo.list_by_tenant(sample_tenant_id)
        assert result.total == 0
        assert len(result.items) == 0


class TestWorkspaceMemberRepository:
    """WorkspaceMemberRepository测试"""

    @pytest.fixture
    def mock_session(self):
        return MockSession()

    @pytest.fixture
    def repo(self, mock_session):
        return WorkspaceMemberRepositoryImpl(mock_session)

    @pytest.fixture
    def sample_member_id(self):
        return uuid4()

    @pytest.fixture
    def sample_ws_id(self):
        return uuid4()

    @pytest.fixture
    def sample_user_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_member(self, repo, mock_session):
        """测试添加成员"""
        member = WorkspaceMember(
            id=uuid4(),
            workspace_id=uuid4(),
            user_id=uuid4(),
            role=WorkspaceRole.MEMBER
        )

        result = await repo.create(member)

        assert member in mock_session.added
        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo, sample_member_id):
        """测试根据ID获取"""
        result = await repo.get_by_id(sample_member_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_workspace_and_user(self, repo, sample_ws_id, sample_user_id):
        """测试根据工作空间和用户获取"""
        result = await repo.get_by_workspace_and_user(sample_ws_id, sample_user_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_workspace(self, repo, sample_ws_id):
        """测试列出工作空间成员"""
        result = await repo.list_by_workspace(sample_ws_id)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_list_by_user(self, repo, sample_user_id):
        """测试列出用户加入的工作空间"""
        result = await repo.list_by_user(sample_user_id)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_update_member(self, repo, mock_session):
        """测试更新成员"""
        member = WorkspaceMember(
            id=uuid4(),
            workspace_id=uuid4(),
            user_id=uuid4(),
            role=WorkspaceRole.MEMBER
        )

        result = await repo.update(member)

        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_delete_member(self, repo, mock_session, sample_member_id):
        """测试删除成员"""
        result = await repo.delete(sample_member_id)

        assert mock_session.flushed is True
