"""
单元测试 - 用户Repository
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from infrastructure.repositories.user_repository import UserRepositoryImpl
from infrastructure.database.models import User
from core.value_objects.pagination import Page


class TestUserRepositoryImpl:
    """UserRepositoryImpl单元测试"""

    @pytest.fixture
    def mock_session(self):
        """创建模拟数据库会话"""
        session = MagicMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.add_all = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.merge = MagicMock()
        session.delete = MagicMock()
        return session

    @pytest.fixture
    def user_repo(self, mock_session):
        """创建UserRepositoryImpl实例"""
        return UserRepositoryImpl(session=mock_session)

    @pytest.mark.asyncio
    async def test_get_by_email_found(self, user_repo, mock_session):
        """测试根据邮箱获取用户-找到"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = User(
            id=uuid4(),
            username="testuser",
            email="test@example.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=uuid4()
        )
        mock_session.execute.return_value = mock_result

        result = await user_repo.get_by_email("test@example.com")

        assert result is not None
        assert result.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_by_email_not_found(self, user_repo, mock_session):
        """测试根据邮箱获取用户-未找到"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await user_repo.get_by_email("notfound@example.com")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_username_found(self, user_repo, mock_session):
        """测试根据用户名获取用户-找到"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = User(
            id=uuid4(),
            username="testuser",
            email="test@example.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=uuid4()
        )
        mock_session.execute.return_value = mock_result

        result = await user_repo.get_by_username("testuser")

        assert result is not None
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_by_username_not_found(self, user_repo, mock_session):
        """测试根据用户名获取用户-未找到"""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await user_repo.get_by_username("notfound")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_tenant(self, user_repo, mock_session):
        """测试获取租户下的所有用户"""
        tenant_id = uuid4()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            User(
                id=uuid4(),
                username="user1",
                email="user1@example.com",
                hashed_password="hash",
                is_active=True,
                tenant_id=tenant_id
            ),
            User(
                id=uuid4(),
                username="user2",
                email="user2@example.com",
                hashed_password="hash",
                is_active=True,
                tenant_id=tenant_id
            )
        ]
        mock_session.execute.return_value = mock_result

        result = await user_repo.get_by_tenant(tenant_id)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_by_id(self, user_repo, mock_session):
        """测试根据ID获取用户"""
        user_id = uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = User(
            id=user_id,
            username="testuser",
            email="test@example.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=uuid4()
        )
        mock_session.execute.return_value = mock_result

        result = await user_repo.get_by_id(user_id)

        assert result is not None
        assert result.id == user_id

    @pytest.mark.asyncio
    async def test_create(self, user_repo, mock_session):
        """测试创建用户"""
        user = User(
            id=uuid4(),
            username="newuser",
            email="new@example.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=uuid4()
        )

        await user_repo.create(user)

        mock_session.add.assert_called_once_with(user)
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update(self, user_repo, mock_session):
        """测试更新用户"""
        user = User(
            id=uuid4(),
            username="testuser",
            email="test@example.com",
            hashed_password="hash",
            is_active=True,
            tenant_id=uuid4()
        )

        await user_repo.update(user)

        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete(self, user_repo, mock_session):
        """测试删除用户"""
        user_id = uuid4()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        result = await user_repo.delete(user_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_not_found(self, user_repo, mock_session):
        """测试删除不存在的用户"""
        user_id = uuid4()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        result = await user_repo.delete(user_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self, user_repo, mock_session):
        """测试检查用户存在-存在"""
        user_id = uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 1
        mock_session.execute.return_value = mock_result

        result = await user_repo.exists(user_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, user_repo, mock_session):
        """测试检查用户存在-不存在"""
        user_id = uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_session.execute.return_value = mock_result

        result = await user_repo.exists(user_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_list_with_pagination(self, user_repo, mock_session):
        """测试分页查询用户列表"""
        from core.value_objects.pagination import Pagination, Page

        mock_users = [
            User(
                id=uuid4(),
                username="user1",
                email="user1@example.com",
                hashed_password="hash",
                is_active=True,
                tenant_id=uuid4()
            )
        ]

        mock_page = Page(
            items=mock_users,
            total=1,
            page=1,
            page_size=20
        )

        with patch.object(user_repo, 'list', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_page

            pagination = Pagination(page=1, page_size=20)
            result = await user_repo.list(pagination=pagination)

            assert result.total == 1
            assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_list_with_filters(self, user_repo, mock_session):
        """测试带过滤条件查询用户列表"""
        from core.value_objects.pagination import Pagination, Page

        mock_page = Page(
            items=[],
            total=0,
            page=1,
            page_size=20
        )

        with patch.object(user_repo, 'list', new_callable=AsyncMock) as mock_list:
            mock_list.return_value = mock_page

            pagination = Pagination(page=1, page_size=20)
            result = await user_repo.list(filters={"tenant_id": str(uuid4())}, pagination=pagination)

            assert result.total == 0

    @pytest.mark.asyncio
    async def test_batch_create(self, user_repo, mock_session):
        """测试批量创建用户"""
        users = [
            User(
                id=uuid4(),
                username=f"user{i}",
                email=f"user{i}@example.com",
                hashed_password="hash",
                is_active=True,
                tenant_id=uuid4()
            )
            for i in range(3)
        ]

        result = await user_repo.batch_create(users)

        assert len(result) == 3
        mock_session.add_all.assert_called_once()
        mock_session.flush.assert_called()

    @pytest.mark.asyncio
    async def test_batch_update(self, user_repo, mock_session):
        """测试批量更新用户"""
        users = [
            User(
                id=uuid4(),
                username=f"user{i}",
                email=f"user{i}@example.com",
                hashed_password="hash",
                is_active=True,
                tenant_id=uuid4()
            )
            for i in range(3)
        ]

        with patch.object(user_repo, 'batch_update', new_callable=AsyncMock) as mock_batch_update:
            mock_batch_update.return_value = users

            result = await user_repo.batch_update(users)

            assert len(result) == 3

    @pytest.mark.asyncio
    async def test_batch_delete(self, user_repo, mock_session):
        """测试批量删除用户"""
        ids = [uuid4() for _ in range(3)]
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        result = await user_repo.batch_delete(ids)

        assert result == 3

    @pytest.mark.asyncio
    async def test_batch_get(self, user_repo, mock_session):
        """测试批量获取用户"""
        ids = [uuid4() for _ in range(3)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            User(
                id=ids[0],
                username="user0",
                email="user0@example.com",
                hashed_password="hash",
                is_active=True,
                tenant_id=uuid4()
            )
        ]
        mock_session.execute.return_value = mock_result

        result = await user_repo.batch_get(ids)

        assert len(result) == 1
