"""
会话权限检查器单元测试

测试PermissionChecker类的核心功能：
1. 创建者完全访问权限
2. 工作空间成员读取权限
3. 租户管理员元数据审计模式
4. 超级管理员完全权限
5. 私有会话访问限制
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from services.permission_checker import (
    PermissionChecker,
    PermissionAction
)
from infrastructure.database.models import ConversationVisibility


@pytest.fixture
def permission_checker():
    """创建PermissionChecker实例"""
    return PermissionChecker()


@pytest.fixture
def mock_session():
    """创建模拟的数据库会话"""
    session = Mock(spec=AsyncSession)
    return session


class TestConversationCreatorAccess:
    """测试Property 4: 创建者完全访问权限"""
    
    @pytest.mark.asyncio
    async def test_creator_can_read_private_conversation(
        self, permission_checker, mock_session
    ):
        """
        Property 4: 创建者对任何可见性级别的会话都有READ权限
        """
        conversation_id = uuid4()
        user_id = str(uuid4())
        
        # 模拟会话对象
        mock_conversation = Mock()
        mock_conversation.user_id = user_id
        mock_conversation.visibility = ConversationVisibility.PRIVATE
        
        # 模拟_get_conversation方法
        permission_checker._get_conversation = AsyncMock(return_value=mock_conversation)
        
        has_permission = await permission_checker.check_conversation_access(
            user_id=user_id,
            conversation_id=conversation_id,
            action=PermissionAction.READ,
            session=mock_session
        )
        
        assert has_permission is True
    
    @pytest.mark.asyncio
    async def test_creator_can_update_workspace_conversation(
        self, permission_checker, mock_session
    ):
        """
        Property 4: 创建者对WORKSPACE会话有UPDATE权限
        """
        conversation_id = uuid4()
        user_id = str(uuid4())
        
        # 模拟会话对象
        mock_conversation = Mock()
        mock_conversation.user_id = user_id
        mock_conversation.visibility = ConversationVisibility.WORKSPACE
        mock_conversation.workspace_id = str(uuid4())
        
        permission_checker._get_conversation = AsyncMock(return_value=mock_conversation)
        
        has_permission = await permission_checker.check_conversation_access(
            user_id=user_id,
            conversation_id=conversation_id,
            action=PermissionAction.UPDATE,
            session=mock_session
        )
        
        assert has_permission is True


class TestPrivateConversationRestriction:
    """测试Property 11: PRIVATE会话访问限制"""
    
    @pytest.mark.asyncio
    async def test_non_creator_cannot_access_private(
        self, permission_checker, mock_session
    ):
        """
        Property 11: 非创建者无法访问PRIVATE会话
        """
        conversation_id = uuid4()
        creator_id = str(uuid4())
        other_user_id = str(uuid4())
        
        # 模拟会话对象（属于creator）
        mock_conversation = Mock()
        mock_conversation.user_id = creator_id
        mock_conversation.visibility = ConversationVisibility.PRIVATE
        
        permission_checker._get_conversation = AsyncMock(return_value=mock_conversation)
        
        # 模拟用户角色信息（普通用户，非超级用户）
        permission_checker.get_user_role_info = AsyncMock(return_value={
            "is_superuser": False,
            "is_tenant_admin": False,
            "tenant_id": None,
            "workspace_roles": {}
        })
        
        has_permission = await permission_checker.check_conversation_access(
            user_id=other_user_id,
            conversation_id=conversation_id,
            action=PermissionAction.READ,
            session=mock_session
        )
        
        assert has_permission is False
    
    @pytest.mark.asyncio
    async def test_non_creator_cannot_update_private(
        self, permission_checker, mock_session
    ):
        """
        Property 23: 非创建者无法更新PRIVATE会话
        """
        conversation_id = uuid4()
        creator_id = str(uuid4())
        other_user_id = str(uuid4())
        
        mock_conversation = Mock()
        mock_conversation.user_id = creator_id
        mock_conversation.visibility = ConversationVisibility.PRIVATE
        
        permission_checker._get_conversation = AsyncMock(return_value=mock_conversation)
        permission_checker.get_user_role_info = AsyncMock(return_value={
            "is_superuser": False,
            "is_tenant_admin": False,
            "tenant_id": None,
            "workspace_roles": {}
        })
        
        has_permission = await permission_checker.check_conversation_access(
            user_id=other_user_id,
            conversation_id=conversation_id,
            action=PermissionAction.UPDATE,
            session=mock_session
        )
        
        assert has_permission is False


class TestSuperuserAccess:
    """测试Property 9: 超级管理员完全权限"""
    
    @pytest.mark.asyncio
    async def test_superuser_can_access_any_conversation(
        self, permission_checker, mock_session
    ):
        """
        Property 9: 超级管理员对任何会话都有完全权限
        """
        conversation_id = uuid4()
        superuser_id = str(uuid4())
        creator_id = str(uuid4())
        
        # 模拟私有会话
        mock_conversation = Mock()
        mock_conversation.user_id = creator_id
        mock_conversation.visibility = ConversationVisibility.PRIVATE
        
        permission_checker._get_conversation = AsyncMock(return_value=mock_conversation)
        permission_checker.get_user_role_info = AsyncMock(return_value={
            "is_superuser": True,
            "is_tenant_admin": False,
            "tenant_id": None,
            "workspace_roles": {}
        })
        
        for action in [PermissionAction.READ, PermissionAction.UPDATE, 
                     PermissionAction.DELETE, PermissionAction.READ_METADATA]:
            has_permission = await permission_checker.check_conversation_access(
                user_id=superuser_id,
                conversation_id=conversation_id,
                action=action,
                session=mock_session
            )
            
            assert has_permission is True, f"Superuser should have {action.value} permission"


class TestTenantAdminMetadataAccess:
    """测试Property 8: 租户管理员元数据审计模式"""
    
    @pytest.mark.asyncio
    async def test_tenant_admin_can_read_metadata_only_for_private(
        self, permission_checker, mock_session
    ):
        """
        Property 8: 租户管理员对PRIVATE会话只能查看元数据，不能查看内容
        """
        conversation_id = uuid4()
        tenant_admin_id = str(uuid4())
        creator_id = str(uuid4())
        tenant_id = str(uuid4())
        
        mock_conversation = Mock()
        mock_conversation.user_id = creator_id
        mock_conversation.visibility = ConversationVisibility.PRIVATE
        mock_conversation.workspace_id = str(uuid4())
        
        permission_checker._get_conversation = AsyncMock(return_value=mock_conversation)
        permission_checker.get_user_role_info = AsyncMock(return_value={
            "is_superuser": False,
            "is_tenant_admin": True,
            "tenant_id": tenant_id,
            "workspace_roles": {}
        })
        
        permission_checker._get_conversation_tenant_id = AsyncMock(return_value=tenant_id)
        
        # 应该允许查看元数据
        can_read_metadata = await permission_checker.check_conversation_access(
            user_id=tenant_admin_id,
            conversation_id=conversation_id,
            action=PermissionAction.READ_METADATA,
            session=mock_session
        )
        assert can_read_metadata is True
        
        # 不应该允许查看内容
        can_read_content = await permission_checker.check_conversation_access(
            user_id=tenant_admin_id,
            conversation_id=conversation_id,
            action=PermissionAction.READ,
            session=mock_session
        )
        assert can_read_content is False
        
        # 不应该允许修改或删除
        can_update = await permission_checker.check_conversation_access(
            user_id=tenant_admin_id,
            conversation_id=conversation_id,
            action=PermissionAction.UPDATE,
            session=mock_session
        )
        assert can_update is False


class TestWorkspaceMemberAccess:
    """测试Property 5: 工作空间成员读取权限"""
    
    @pytest.mark.asyncio
    async def test_workspace_member_can_read_workspace_conversation(
        self, permission_checker, mock_session
    ):
        """
        Property 5: 工作空间成员可以读取WORKSPACE会话
        """
        conversation_id = uuid4()
        workspace_id = str(uuid4())
        member_id = str(uuid4())
        creator_id = str(uuid4())
        
        mock_conversation = Mock()
        mock_conversation.user_id = creator_id
        mock_conversation.visibility = ConversationVisibility.WORKSPACE
        mock_conversation.workspace_id = workspace_id
        
        permission_checker._get_conversation = AsyncMock(return_value=mock_conversation)
        permission_checker.get_user_role_info = AsyncMock(return_value={
            "is_superuser": False,
            "is_tenant_admin": False,
            "tenant_id": None,
            "workspace_roles": {
                workspace_id: "member"
            }
        })
        
        has_permission = await permission_checker.check_conversation_access(
            user_id=member_id,
            conversation_id=conversation_id,
            action=PermissionAction.READ,
            session=mock_session
        )
        
        assert has_permission is True
    
    @pytest.mark.asyncio
    async def test_workspace_member_cannot_update_workspace_conversation(
        self, permission_checker, mock_session
    ):
        """
        Property 7: 工作空间成员不能修改WORKSPACE会话（只有管理员可以）
        """
        conversation_id = uuid4()
        workspace_id = str(uuid4())
        member_id = str(uuid4())
        creator_id = str(uuid4())
        
        mock_conversation = Mock()
        mock_conversation.user_id = creator_id
        mock_conversation.visibility = ConversationVisibility.WORKSPACE
        mock_conversation.workspace_id = workspace_id
        
        permission_checker._get_conversation = AsyncMock(return_value=mock_conversation)
        permission_checker.get_user_role_info = AsyncMock(return_value={
            "is_superuser": False,
            "is_tenant_admin": False,
            "tenant_id": None,
            "workspace_roles": {
                workspace_id: "member"
            }
        })
        
        has_permission = await permission_checker.check_conversation_access(
            user_id=member_id,
            conversation_id=conversation_id,
            action=PermissionAction.UPDATE,
            session=mock_session
        )
        
        assert has_permission is False


class TestConversationNotFound:
    """测试会话不存在的情况"""
    
    @pytest.mark.asyncio
    async def test_return_false_when_conversation_not_found(
        self, permission_checker, mock_session
    ):
        """当会话不存在时返回False"""
        conversation_id = uuid4()
        user_id = str(uuid4())
        
        permission_checker._get_conversation = AsyncMock(return_value=None)
        
        has_permission = await permission_checker.check_conversation_access(
            user_id=user_id,
            conversation_id=conversation_id,
            action=PermissionAction.READ,
            session=mock_session
        )
        
        assert has_permission is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
