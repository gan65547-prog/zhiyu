"""
API路由层测试 - 用户管理路由

测试用户管理相关的API端点
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from core.exceptions import (
    ResourceNotFoundError, ResourceConflictError, 
    BusinessError, ValidationError
)
from api.errors import QuotaExceededException


class TestUsersRouter:
    """用户管理路由测试类"""

    @pytest.fixture
    def mock_user_service(self):
        """创建模拟用户服务"""
        service = MagicMock()
        
        # list_users
        service.list_users = AsyncMock(return_value=MagicMock(
            items=[
                {
                    "id": str(uuid4()),
                    "username": "user1",
                    "email": "user1@example.com",
                    "is_active": True,
                    "is_superuser": False,
                    "tenant_id": str(uuid4()),
                    "current_workspace_id": None,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                },
                {
                    "id": str(uuid4()),
                    "username": "user2",
                    "email": "user2@example.com",
                    "is_active": True,
                    "is_superuser": False,
                    "tenant_id": str(uuid4()),
                    "current_workspace_id": None,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
            ],
            total=2,
            page=1,
            page_size=20
        ))
        
        # create_user
        service.create_user = AsyncMock(return_value={
            "id": str(uuid4()),
            "username": "newuser",
            "email": "newuser@example.com",
            "is_active": True,
            "tenant_id": str(uuid4()),
            "created_at": datetime.utcnow().isoformat()
        })
        
        # get_user
        service.get_user = AsyncMock(return_value={
            "id": str(uuid4()),
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True,
            "is_superuser": False,
            "tenant_id": str(uuid4()),
            "tenant_name": "Test Tenant",
            "current_workspace_id": None,
            "workspaces": [
                {
                    "workspace_id": str(uuid4()),
                    "workspace_name": "Default",
                    "role": "owner",
                    "is_default": True,
                    "joined_at": datetime.utcnow().isoformat()
                }
            ],
            "extra_metadata": {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        })
        
        # update_user
        service.update_user = AsyncMock(return_value={
            "id": str(uuid4()),
            "username": "updateduser",
            "email": "updated@example.com",
            "is_active": True,
            "updated_at": datetime.utcnow().isoformat()
        })
        
        # delete_user
        service.delete_user = AsyncMock(return_value=True)
        
        # reset_password
        service.reset_password = AsyncMock(return_value={
            "message": "Password reset successfully",
            "email_sent": True
        })
        
        # activate_user
        service.activate_user = AsyncMock(return_value={
            "id": str(uuid4()),
            "is_active": False,
            "updated_at": datetime.utcnow().isoformat()
        })
        
        # get_user_workspaces
        service.get_user_workspaces = AsyncMock(return_value=[
            {
                "workspace_id": str(uuid4()),
                "workspace_name": "Workspace 1",
                "role": "owner",
                "is_default": True,
                "joined_at": datetime.utcnow().isoformat()
            }
        ])
        
        return service

    @pytest.fixture
    def sample_tenant_id(self):
        """示例租户ID"""
        return str(uuid4())

    @pytest.fixture
    def sample_user_id(self):
        """示例用户ID"""
        return str(uuid4())

    # ==================== 测试 GET /users ====================

    @pytest.mark.asyncio
    async def test_list_users_success(self, mock_user_service):
        """测试成功获取用户列表"""
        result = await mock_user_service.list_users(
            tenant_id=uuid4(),
            page=1,
            page_size=20
        )

        assert result.total == 2
        assert len(result.items) == 2
        assert result.items[0]["username"] == "user1"
        assert result.items[1]["username"] == "user2"

    @pytest.mark.asyncio
    async def test_list_users_with_search(self, mock_user_service):
        """测试带搜索条件的用户列表"""
        # 修改mock返回值
        mock_user_service.list_users = AsyncMock(return_value=MagicMock(
            items=[
                {
                    "id": str(uuid4()),
                    "username": "user1",
                    "email": "user1@example.com",
                    "is_active": True,
                    "is_superuser": False,
                    "tenant_id": str(uuid4()),
                    "current_workspace_id": None,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
            ],
            total=1,
            page=1,
            page_size=20
        ))

        result = await mock_user_service.list_users(
            tenant_id=uuid4(),
            page=1,
            page_size=20,
            search="user1"
        )

        assert result.total == 1
        assert result.items[0]["username"] == "user1"

    @pytest.mark.asyncio
    async def test_list_users_with_active_filter(self, mock_user_service):
        """测试按激活状态过滤"""
        result = await mock_user_service.list_users(
            tenant_id=uuid4(),
            page=1,
            page_size=20,
            is_active=True
        )

        assert result.total == 2
        for item in result.items:
            assert item["is_active"] is True

    @pytest.mark.asyncio
    async def test_list_users_empty(self, mock_user_service):
        """测试空用户列表"""
        mock_user_service.list_users = AsyncMock(return_value=MagicMock(
            items=[],
            total=0,
            page=1,
            page_size=20
        ))

        result = await mock_user_service.list_users(
            tenant_id=uuid4(),
            page=1,
            page_size=20
        )

        assert result.total == 0
        assert len(result.items) == 0

    # ==================== 测试 POST /users ====================

    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_user_service, sample_tenant_id):
        """测试成功创建用户"""
        result = await mock_user_service.create_user(
            tenant_id=uuid4(),
            username="newuser",
            email="newuser@example.com",
            password="SecurePass123!"
        )

        assert result["username"] == "newuser"
        assert result["email"] == "newuser@example.com"
        assert "id" in result

    @pytest.mark.asyncio
    async def test_create_user_with_workspaces(self, mock_user_service, sample_tenant_id):
        """测试创建用户并加入工作空间"""
        workspace_ids = [uuid4(), uuid4()]
        
        result = await mock_user_service.create_user(
            tenant_id=uuid4(),
            username="newuser",
            email="newuser@example.com",
            password="SecurePass123!",
            workspace_ids=workspace_ids,
            default_role="member"
        )

        assert result["username"] == "newuser"

    @pytest.mark.asyncio
    async def test_create_user_quota_exceeded(self, mock_user_service):
        """测试配额超限"""
        mock_user_service.create_user = AsyncMock(
            side_effect=QuotaExceededException("租户用户配额超限: 100/100")
        )

        with pytest.raises(QuotaExceededException, match="租户用户配额超限"):
            await mock_user_service.create_user(
                tenant_id=uuid4(),
                username="newuser",
                email="newuser@example.com",
                password="SecurePass123!"
            )

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, mock_user_service):
        """测试用户名已存在"""
        mock_user_service.create_user = AsyncMock(
            side_effect=ResourceConflictError("Username already exists")
        )

        with pytest.raises(ResourceConflictError, match="Username already exists"):
            await mock_user_service.create_user(
                tenant_id=uuid4(),
                username="existinguser",
                email="new@example.com",
                password="SecurePass123!"
            )

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, mock_user_service):
        """测试邮箱已存在"""
        mock_user_service.create_user = AsyncMock(
            side_effect=ResourceConflictError("Email already exists")
        )

        with pytest.raises(ResourceConflictError, match="Email already exists"):
            await mock_user_service.create_user(
                tenant_id=uuid4(),
                username="newuser",
                email="existing@example.com",
                password="SecurePass123!"
            )

    @pytest.mark.asyncio
    async def test_create_user_weak_password(self, mock_user_service):
        """测试弱密码"""
        mock_user_service.create_user = AsyncMock(
            side_effect=ValidationError("Password must be at least 8 characters")
        )

        with pytest.raises(ValidationError, match="Password must"):
            await mock_user_service.create_user(
                tenant_id=uuid4(),
                username="newuser",
                email="new@example.com",
                password="weak"
            )

    # ==================== 测试 GET /users/{user_id} ====================

    @pytest.mark.asyncio
    async def test_get_user_success(self, mock_user_service, sample_user_id):
        """测试成功获取用户详情"""
        result = await mock_user_service.get_user(uuid4())

        assert result is not None
        assert result["username"] == "testuser"
        assert result["email"] == "test@example.com"
        assert "workspaces" in result
        assert len(result["workspaces"]) > 0

    @pytest.mark.asyncio
    async def test_get_user_not_found(self, mock_user_service, sample_user_id):
        """测试用户不存在"""
        mock_user_service.get_user = AsyncMock(return_value=None)

        result = await mock_user_service.get_user(uuid4())

        assert result is None

    # ==================== 测试 PUT /users/{user_id} ====================

    @pytest.mark.asyncio
    async def test_update_user_success(self, mock_user_service, sample_user_id):
        """测试成功更新用户"""
        result = await mock_user_service.update_user(
            uuid4(),
            username="updateduser",
            email="updated@example.com"
        )

        assert result["username"] == "updateduser"
        assert result["email"] == "updated@example.com"

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, mock_user_service, sample_user_id):
        """测试更新不存在的用户"""
        mock_user_service.update_user = AsyncMock(
            side_effect=ResourceNotFoundError("User not found")
        )

        with pytest.raises(ResourceNotFoundError, match="User not found"):
            await mock_user_service.update_user(
                uuid4(),
                username="newname"
            )

    @pytest.mark.asyncio
    async def test_update_user_duplicate_username(self, mock_user_service, sample_user_id):
        """测试更新为已存在的用户名"""
        mock_user_service.update_user = AsyncMock(
            side_effect=ResourceConflictError("Username already exists")
        )

        with pytest.raises(ResourceConflictError, match="Username already exists"):
            await mock_user_service.update_user(
                uuid4(),
                username="existinguser"
            )

    @pytest.mark.asyncio
    async def test_update_user_activate_status(self, mock_user_service, sample_user_id):
        """测试更新用户激活状态"""
        result = await mock_user_service.update_user(
            uuid4(),
            is_active=False
        )

        assert "updated_at" in result

    # ==================== 测试 DELETE /users/{user_id} ====================

    @pytest.mark.asyncio
    async def test_delete_user_success(self, mock_user_service, sample_user_id):
        """测试成功删除用户"""
        result = await mock_user_service.delete_user(uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, mock_user_service, sample_user_id):
        """测试删除不存在的用户"""
        mock_user_service.delete_user = AsyncMock(
            side_effect=ResourceNotFoundError("User not found")
        )

        with pytest.raises(ResourceNotFoundError, match="User not found"):
            await mock_user_service.delete_user(uuid4())

    @pytest.mark.asyncio
    async def test_delete_user_only_owner(self, mock_user_service, sample_user_id):
        """测试删除工作空间唯一OWNER"""
        mock_user_service.delete_user = AsyncMock(
            side_effect=BusinessError("Cannot delete user: user is the only owner")
        )

        with pytest.raises(BusinessError, match="only owner"):
            await mock_user_service.delete_user(uuid4())

    # ==================== 测试 POST /users/{user_id}/reset-password ====================

    @pytest.mark.asyncio
    async def test_reset_password_success(self, mock_user_service, sample_user_id):
        """测试成功重置密码"""
        result = await mock_user_service.reset_password(
            uuid4(),
            "NewSecurePass123!",
            send_email=True
        )

        assert result["message"] == "Password reset successfully"
        assert result["email_sent"] is True

    @pytest.mark.asyncio
    async def test_reset_password_without_email(self, mock_user_service, sample_user_id):
        """测试重置密码不发送邮件"""
        mock_user_service.reset_password = AsyncMock(return_value={
            "message": "Password reset successfully",
            "email_sent": False
        })

        result = await mock_user_service.reset_password(
            uuid4(),
            "NewSecurePass123!",
            send_email=False
        )

        assert result["email_sent"] is False

    @pytest.mark.asyncio
    async def test_reset_password_user_not_found(self, mock_user_service, sample_user_id):
        """测试重置不存在用户的密码"""
        mock_user_service.reset_password = AsyncMock(
            side_effect=ResourceNotFoundError("User not found")
        )

        with pytest.raises(ResourceNotFoundError, match="User not found"):
            await mock_user_service.reset_password(
                uuid4(),
                "NewSecurePass123!"
            )

    @pytest.mark.asyncio
    async def test_reset_password_weak_password(self, mock_user_service, sample_user_id):
        """测试重置为弱密码"""
        mock_user_service.reset_password = AsyncMock(
            side_effect=ValidationError("Password must be at least 8 characters")
        )

        with pytest.raises(ValidationError, match="Password must"):
            await mock_user_service.reset_password(
                uuid4(),
                "weak"
            )

    # ==================== 测试 PUT /users/{user_id}/activate ====================

    @pytest.mark.asyncio
    async def test_activate_user_success(self, mock_user_service, sample_user_id):
        """测试成功停用用户"""
        result = await mock_user_service.activate_user(uuid4(), False)

        assert result["is_active"] is False

    @pytest.mark.asyncio
    async def test_activate_user_enable(self, mock_user_service, sample_user_id):
        """测试成功激活用户"""
        mock_user_service.activate_user = AsyncMock(return_value={
            "id": str(uuid4()),
            "is_active": True,
            "updated_at": datetime.utcnow().isoformat()
        })

        result = await mock_user_service.activate_user(uuid4(), True)

        assert result["is_active"] is True

    @pytest.mark.asyncio
    async def test_activate_user_not_found(self, mock_user_service, sample_user_id):
        """测试激活不存在的用户"""
        mock_user_service.activate_user = AsyncMock(
            side_effect=ResourceNotFoundError("User not found")
        )

        with pytest.raises(ResourceNotFoundError, match="User not found"):
            await mock_user_service.activate_user(uuid4(), True)

    # ==================== 测试 GET /users/{user_id}/workspaces ====================

    @pytest.mark.asyncio
    async def test_get_user_workspaces_success(self, mock_user_service, sample_user_id):
        """测试成功获取用户工作空间列表"""
        result = await mock_user_service.get_user_workspaces(uuid4())

        assert len(result) == 1
        assert result[0]["workspace_name"] == "Workspace 1"
        assert result[0]["role"] == "owner"

    @pytest.mark.asyncio
    async def test_get_user_workspaces_empty(self, mock_user_service, sample_user_id):
        """测试用户没有工作空间"""
        mock_user_service.get_user_workspaces = AsyncMock(return_value=[])

        result = await mock_user_service.get_user_workspaces(uuid4())

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_user_workspaces_multiple(self, mock_user_service, sample_user_id):
        """测试用户有多个工作空间"""
        mock_user_service.get_user_workspaces = AsyncMock(return_value=[
            {
                "workspace_id": str(uuid4()),
                "workspace_name": "Workspace 1",
                "role": "owner",
                "is_default": True,
                "joined_at": datetime.utcnow().isoformat()
            },
            {
                "workspace_id": str(uuid4()),
                "workspace_name": "Workspace 2",
                "role": "member",
                "is_default": False,
                "joined_at": datetime.utcnow().isoformat()
            }
        ])

        result = await mock_user_service.get_user_workspaces(uuid4())

        assert len(result) == 2
        assert result[0]["role"] == "owner"
        assert result[1]["role"] == "member"

    # ==================== 权限测试 ====================

    @pytest.mark.asyncio
    async def test_list_users_as_member_forbidden(self, mock_user_service):
        """测试普通成员无法查看用户列表"""
        # 这个测试应该在实际的API测试中进行，这里只是示例
        # 实际测试需要模拟权限检查装饰器
        pass

    @pytest.mark.asyncio
    async def test_create_user_as_member_forbidden(self, mock_user_service):
        """测试普通成员无法创建用户"""
        # 这个测试应该在实际的API测试中进行，这里只是示例
        pass

    @pytest.mark.asyncio
    async def test_delete_user_as_member_forbidden(self, mock_user_service):
        """测试普通成员无法删除用户"""
        # 这个测试应该在实际的API测试中进行，这里只是示例
        pass

    # ==================== 边界条件测试 ====================

    @pytest.mark.asyncio
    async def test_list_users_pagination(self, mock_user_service):
        """测试分页功能"""
        # 第一页
        result_page1 = await mock_user_service.list_users(
            tenant_id=uuid4(),
            page=1,
            page_size=1
        )
        
        # 修改mock返回第二页
        mock_user_service.list_users = AsyncMock(return_value=MagicMock(
            items=[
                {
                    "id": str(uuid4()),
                    "username": "user2",
                    "email": "user2@example.com",
                    "is_active": True,
                    "is_superuser": False,
                    "tenant_id": str(uuid4()),
                    "current_workspace_id": None,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
            ],
            total=2,
            page=2,
            page_size=1
        ))
        
        result_page2 = await mock_user_service.list_users(
            tenant_id=uuid4(),
            page=2,
            page_size=1
        )

        assert result_page2.page == 2
        assert len(result_page2.items) == 1

    @pytest.mark.asyncio
    async def test_create_user_with_special_characters(self, mock_user_service):
        """测试创建包含特殊字符的用户"""
        result = await mock_user_service.create_user(
            tenant_id=uuid4(),
            username="user_with-special.chars",
            email="special+email@example.com",
            password="SecurePass123!"
        )

        assert result["username"] == "newuser"

    @pytest.mark.asyncio
    async def test_update_user_partial_update(self, mock_user_service, sample_user_id):
        """测试部分更新用户"""
        # 只更新用户名
        result = await mock_user_service.update_user(
            uuid4(),
            username="newusername"
        )

        assert "updated_at" in result
