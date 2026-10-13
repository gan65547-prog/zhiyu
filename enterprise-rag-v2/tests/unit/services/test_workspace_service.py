"""
WorkspaceService单元测试
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from services.impl.workspace_service import WorkspaceServiceImpl
from infrastructure.database.models import Workspace, WorkspaceMember, User, WorkspaceRole
from core.value_objects.pagination import Pagination, Page


class MockWorkspaceRepo:
    """模拟工作空间Repository"""
    def __init__(self):
        self.workspaces = {}
        self._member_repo = None

    async def get_by_id(self, workspace_id):
        return self.workspaces.get(workspace_id)

    async def create(self, workspace):
        if not workspace.id:
            workspace.id = uuid4()
        if not workspace.created_at:
            workspace.created_at = datetime.utcnow()
        if not workspace.updated_at:
            workspace.updated_at = datetime.utcnow()
        self.workspaces[workspace.id] = workspace
        return workspace

    async def update(self, workspace):
        if not workspace.updated_at:
            workspace.updated_at = datetime.utcnow()
        self.workspaces[workspace.id] = workspace
        return workspace

    async def delete(self, workspace_id):
        if workspace_id in self.workspaces:
            del self.workspaces[workspace_id]
            return True
        return False

    async def list_by_tenant(self, tenant_id, keyword=None, pagination=None):
        items = [ws for ws in self.workspaces.values() if ws.tenant_id == tenant_id]

        if keyword:
            items = [ws for ws in items if keyword.lower() in ws.name.lower()]

        total = len(items)
        page = pagination.page if pagination else 1
        page_size = pagination.page_size if pagination else 20
        start = (page - 1) * page_size
        end = start + page_size

        return MagicMock(items=items[start:end], total=total, page=page, page_size=page_size)

    async def list_by_user_and_tenant(self, user_id, tenant_id, keyword=None, pagination=None):
        """与实现一致：仅返回当前用户为成员的工作空间。"""
        tenant_id_str = str(tenant_id)
        user_id_str = str(user_id)
        member_ws = set()
        if self._member_repo:
            for m in self._member_repo.members.values():
                if str(m.user_id) == user_id_str:
                    member_ws.add(str(m.workspace_id))

        items = []
        for ws in self.workspaces.values():
            if str(ws.tenant_id) != tenant_id_str:
                continue
            if str(ws.id) not in member_ws:
                continue
            if keyword and keyword.lower() not in (ws.name or "").lower():
                continue
            items.append(ws)

        total = len(items)
        page = pagination.page if pagination else 1
        page_size = pagination.page_size if pagination else 20
        start = (page - 1) * page_size
        end = start + page_size
        return Page(items=items[start:end], total=total, page=page, page_size=page_size)


class MockMemberRepo:
    """模拟成员Repository"""
    def __init__(self):
        self.members = {}

    async def get_by_id(self, member_id):
        for m in self.members.values():
            if m.id == member_id:
                return m
        return None

    async def get_by_workspace_and_user(self, workspace_id, user_id):
        for m in self.members.values():
            if str(m.workspace_id) == str(workspace_id) and str(m.user_id) == str(user_id):
                return m
        return None

    async def create(self, member):
        if not member.id:
            member.id = uuid4()
        if not member.joined_at:
            member.joined_at = datetime.utcnow()
        self.members[member.id] = member
        return member

    async def update(self, member):
        self.members[member.id] = member
        return member

    async def delete(self, member_id):
        if member_id in self.members:
            del self.members[member_id]
            return True
        return False

    async def list_by_workspace(self, workspace_id):
        return [m for m in self.members.values() if str(m.workspace_id) == str(workspace_id)]


class TestWorkspaceService:
    """WorkspaceService测试"""

    @pytest.fixture
    def mock_session(self):
        """创建模拟数据库会话"""
        session = MagicMock()
        result = MagicMock()
        result.all.return_value = []
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)
        session.flush = AsyncMock()
        session.add = MagicMock()
        session.get = AsyncMock(return_value=None)
        return session

    @pytest.fixture
    def workspace_service(self, mock_session):
        """创建WorkspaceServiceImpl实例"""
        service = WorkspaceServiceImpl(session=mock_session)
        wr = MockWorkspaceRepo()
        mr = MockMemberRepo()
        wr._member_repo = mr
        service.workspace_repo = wr
        service.member_repo = mr
        service._cleanup_workspace_files = AsyncMock()
        service._cleanup_workspace_vector_collection = AsyncMock()
        service._sync_tenant_admin_workspace_memberships = AsyncMock()
        return service

    @pytest.fixture
    def sample_tenant_id(self):
        return uuid4()

    @pytest.fixture
    def sample_workspace_id(self):
        return uuid4()

    @pytest.fixture
    def sample_user_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_workspace_success(self, workspace_service, sample_tenant_id, sample_user_id):
        """测试创建工作空间成功"""
        result = await workspace_service.create_workspace(
            tenant_id=sample_tenant_id,
            name="Test Workspace",
            description="A test workspace",
            creator_id=sample_user_id,
        )

        assert result["name"] == "Test Workspace"
        assert result["description"] == "A test workspace"
        assert result["tenant_id"] == str(sample_tenant_id)

    @pytest.mark.asyncio
    async def test_create_workspace_with_metadata(self, workspace_service, sample_tenant_id, sample_user_id):
        """测试创建带元数据的工作空间"""
        metadata = {"color": "blue", "icon": "folder"}
        result = await workspace_service.create_workspace(
            tenant_id=sample_tenant_id,
            name="Workspace with Metadata",
            metadata=metadata,
            creator_id=sample_user_id,
        )

        assert result["metadata"]["color"] == "blue"
        assert result["metadata"]["icon"] == "folder"

    @pytest.mark.asyncio
    async def test_get_workspace_success(self, workspace_service, sample_tenant_id):
        """测试获取工作空间详情"""
        workspace_id = uuid4()
        ws = Workspace(
            id=workspace_id,
            tenant_id=sample_tenant_id,
            name="Test WS",
            description="Test",
            metadata={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        workspace_service.workspace_repo.workspaces[workspace_id] = ws

        result = await workspace_service.get_workspace(workspace_id)

        assert result is not None
        assert result["name"] == "Test WS"
        assert result["id"] == str(workspace_id)

    @pytest.mark.asyncio
    async def test_get_workspace_not_found(self, workspace_service, sample_workspace_id):
        """测试获取不存在的工作空间"""
        result = await workspace_service.get_workspace(sample_workspace_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_workspace_success(self, workspace_service, sample_tenant_id):
        """测试更新工作空间"""
        workspace_id = uuid4()
        ws = Workspace(
            id=workspace_id,
            tenant_id=sample_tenant_id,
            name="Old Name",
            description="Old Description",
            metadata={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        workspace_service.workspace_repo.workspaces[workspace_id] = ws

        result = await workspace_service.update_workspace(
            workspace_id=workspace_id,
            name="New Name",
            description="New Description"
        )

        assert result["name"] == "New Name"
        assert result["description"] == "New Description"

    @pytest.mark.asyncio
    async def test_update_workspace_not_found(self, workspace_service, sample_workspace_id):
        """测试更新不存在的工作空间"""
        with pytest.raises(ValueError, match="工作空间不存在"):
            await workspace_service.update_workspace(
                workspace_id=sample_workspace_id,
                name="New Name"
            )

    @pytest.mark.asyncio
    async def test_update_workspace_partial(self, workspace_service, sample_tenant_id):
        """测试部分更新工作空间"""
        workspace_id = uuid4()
        ws = Workspace(
            id=workspace_id,
            tenant_id=sample_tenant_id,
            name="Original",
            description="Original Desc",
            metadata={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        workspace_service.workspace_repo.workspaces[workspace_id] = ws

        result = await workspace_service.update_workspace(
            workspace_id=workspace_id,
            name="Updated Only"
        )

        assert result["name"] == "Updated Only"
        assert result["description"] == "Original Desc"

    @pytest.mark.asyncio
    async def test_delete_workspace_success(self, workspace_service, sample_tenant_id):
        """测试删除工作空间"""
        workspace_id = uuid4()
        ws = Workspace(
            id=workspace_id,
            tenant_id=sample_tenant_id,
            name="To Delete",
            description="",
            metadata={}
        )
        workspace_service.workspace_repo.workspaces[workspace_id] = ws

        result = await workspace_service.delete_workspace(workspace_id)

        assert result is True
        assert workspace_id not in workspace_service.workspace_repo.workspaces

    @pytest.mark.asyncio
    async def test_delete_workspace_not_found(self, workspace_service, sample_workspace_id):
        """测试删除不存在的工作空间"""
        result = await workspace_service.delete_workspace(sample_workspace_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_list_workspaces_empty(self, workspace_service, sample_tenant_id, sample_user_id):
        """测试查询空工作空间列表"""
        result = await workspace_service.list_workspaces(sample_tenant_id, sample_user_id)

        assert result.total == 0
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_list_workspaces_with_data(self, workspace_service, sample_tenant_id, sample_user_id):
        """测试查询工作空间列表"""
        for i in range(3):
            ws = Workspace(
                id=uuid4(),
                tenant_id=str(sample_tenant_id),
                name=f"Workspace {i}",
                description=f"Desc {i}",
                metadata={},
                created_at=datetime.utcnow()
            )
            workspace_service.workspace_repo.workspaces[ws.id] = ws
            await workspace_service.member_repo.create(
                WorkspaceMember(
                    workspace_id=str(ws.id),
                    user_id=str(sample_user_id),
                    role=WorkspaceRole.MEMBER,
                )
            )

        result = await workspace_service.list_workspaces(sample_tenant_id, sample_user_id)

        assert result.total == 3
        assert len(result.items) == 3

    @pytest.mark.asyncio
    async def test_list_workspaces_with_keyword(self, workspace_service, sample_tenant_id, sample_user_id):
        """测试按关键字筛选工作空间"""
        for name in ["Alpha Workspace", "Beta Workspace", "Gamma Project"]:
            ws = Workspace(
                id=uuid4(),
                tenant_id=str(sample_tenant_id),
                name=name,
                description="",
                metadata={},
                created_at=datetime.utcnow()
            )
            workspace_service.workspace_repo.workspaces[ws.id] = ws
            await workspace_service.member_repo.create(
                WorkspaceMember(
                    workspace_id=str(ws.id),
                    user_id=str(sample_user_id),
                    role=WorkspaceRole.MEMBER,
                )
            )

        result = await workspace_service.list_workspaces(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            keyword="workspace",
        )

        assert result.total == 2

    @pytest.mark.asyncio
    async def test_list_workspaces_pagination(self, workspace_service, sample_tenant_id, sample_user_id):
        """测试工作空间列表分页"""
        for i in range(25):
            ws = Workspace(
                id=uuid4(),
                tenant_id=str(sample_tenant_id),
                name=f"Workspace {i}",
                description="",
                metadata={},
                created_at=datetime.utcnow()
            )
            workspace_service.workspace_repo.workspaces[ws.id] = ws
            await workspace_service.member_repo.create(
                WorkspaceMember(
                    workspace_id=str(ws.id),
                    user_id=str(sample_user_id),
                    role=WorkspaceRole.MEMBER,
                )
            )

        pagination = Pagination(page=2, page_size=10)
        result = await workspace_service.list_workspaces(
            tenant_id=sample_tenant_id,
            user_id=sample_user_id,
            pagination=pagination,
        )

        assert result.total == 25
        assert len(result.items) == 10
        assert result.page == 2

    @pytest.mark.asyncio
    async def test_add_member_success(self, workspace_service, sample_workspace_id, sample_user_id):
        """测试添加工作空间成员"""
        result = await workspace_service.add_member(
            workspace_id=sample_workspace_id,
            user_id=sample_user_id,
            role="member"
        )

        assert result["workspace_id"] == str(sample_workspace_id)
        assert result["user_id"] == str(sample_user_id)
        assert result["role"] == "member"

    @pytest.mark.asyncio
    async def test_add_member_already_exists(self, workspace_service, sample_workspace_id, sample_user_id):
        """测试添加已存在的成员"""
        await workspace_service.add_member(
            workspace_id=sample_workspace_id,
            user_id=sample_user_id,
            role="member"
        )

        with pytest.raises(ValueError, match="用户已是工作空间成员"):
            await workspace_service.add_member(
                workspace_id=sample_workspace_id,
                user_id=sample_user_id,
                role="admin"
            )

    @pytest.mark.asyncio
    async def test_add_member_with_role(self, workspace_service, sample_workspace_id, sample_user_id):
        """测试添加不同角色的成员"""
        for role in ["owner", "admin", "member", "viewer"]:
            user_id = uuid4()
            result = await workspace_service.add_member(
                workspace_id=sample_workspace_id,
                user_id=user_id,
                role=role
            )
            assert result["role"] == role

    @pytest.mark.asyncio
    async def test_remove_member_success(self, workspace_service, sample_workspace_id, sample_user_id):
        """测试移除工作空间成员"""
        await workspace_service.add_member(
            workspace_id=sample_workspace_id,
            user_id=sample_user_id,
            role="member"
        )

        result = await workspace_service.remove_member(sample_workspace_id, sample_user_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_remove_member_not_found(self, workspace_service, sample_workspace_id, sample_user_id):
        """测试移除不存在的成员"""
        result = await workspace_service.remove_member(sample_workspace_id, sample_user_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_update_member_role_success(self, workspace_service, sample_workspace_id, sample_user_id):
        """测试更新成员角色"""
        await workspace_service.add_member(
            workspace_id=sample_workspace_id,
            user_id=sample_user_id,
            role="member"
        )

        result = await workspace_service.update_member_role(
            workspace_id=sample_workspace_id,
            user_id=sample_user_id,
            role="admin"
        )

        assert result["role"] == "admin"

    @pytest.mark.asyncio
    async def test_update_member_role_not_found(self, workspace_service, sample_workspace_id, sample_user_id):
        """测试更新不存在成员的角色"""
        with pytest.raises(ValueError, match="成员不存在"):
            await workspace_service.update_member_role(
                workspace_id=sample_workspace_id,
                user_id=sample_user_id,
                role="admin"
            )

    @pytest.mark.asyncio
    async def test_list_members_empty(self, workspace_service, sample_workspace_id):
        """测试查询空成员列表"""
        result = await workspace_service.list_members(sample_workspace_id)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_members_with_data(self, workspace_service, sample_workspace_id):
        """测试查询成员列表"""
        user_ids = [uuid4() for _ in range(3)]
        for user_id in user_ids:
            await workspace_service.add_member(
                workspace_id=sample_workspace_id,
                user_id=user_id,
                role="member"
            )

        result = await workspace_service.list_members(sample_workspace_id)

        assert len(result) == 3
