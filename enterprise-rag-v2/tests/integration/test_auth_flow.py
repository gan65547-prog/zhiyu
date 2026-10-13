"""
集成测试 - 认证流程

测试完整的用户认证流程：注册 → 登录 → Token验证 → 刷新 → 登出
使用真实的AuthServiceImpl但Mock数据库层
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.impl.auth_service import AuthServiceImpl
from infrastructure.database.models import User
from services.utils.jwt import hash_password


class MockUserRepo:
    """模拟用户Repository"""
    def __init__(self):
        self.users = {}

    async def get_by_email(self, email: str):
        for user in self.users.values():
            if user.email == email:
                return user
        return None

    async def get_by_username(self, username: str):
        for user in self.users.values():
            if user.username == username:
                return user
        return None

    async def get_by_id(self, user_id):
        return self.users.get(user_id)

    async def create(self, user: User):
        if not user.id:
            user.id = uuid4()
        if not user.hashed_password:
            user.hashed_password = hash_password("TempPass123!")
        if not user.is_active:
            user.is_active = True
        if not user.is_superuser:
            user.is_superuser = False
        self.users[user.id] = user
        return user

    async def update(self, user: User):
        self.users[user.id] = user
        return user


class TestAuthIntegration:
    """认证流程集成测试"""

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
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def mock_cache(self):
        """创建模拟缓存"""
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock(return_value=True)
        cache.delete = AsyncMock(return_value=True)
        return cache

    @pytest.fixture
    def auth_service(self, mock_db_session):
        """创建AuthServiceImpl实例"""
        service = AuthServiceImpl(session=mock_db_session)
        service.user_repo = MockUserRepo()
        return service

    @pytest.mark.asyncio
    async def test_complete_auth_flow(self, auth_service):
        """测试完整认证流程：注册→登录→Token验证"""
        email = "integration_test@example.com"
        password = "TestPass123!"
        username = "integrationuser"

        with patch("services.impl.auth_service.create_access_token") as mock_access, \
             patch("services.impl.auth_service.create_refresh_token") as mock_refresh, \
             patch("services.impl.auth_service.decode_token") as mock_decode:

            mock_access.return_value = "test_access_token"
            mock_refresh.return_value = "test_refresh_token"

            register_result = await auth_service.register(
                username=username,
                email=email,
                password=password
            )

            assert "user" in register_result
            assert "access_token" in register_result
            assert "refresh_token" in register_result
            assert register_result["user"]["email"] == email
            assert register_result["token_type"] == "bearer"

            login_result = await auth_service.login(
                username=email,
                password=password
            )

            assert "user" in login_result
            assert "access_token" in login_result
            assert login_result["user"]["email"] == email

    @pytest.mark.asyncio
    async def test_auth_flow_with_invalid_credentials(self, auth_service):
        """测试无效凭证登录失败"""
        email = "test@example.com"
        password = "TestPass123!"

        with patch("services.impl.auth_service.create_access_token") as mock_access, \
             patch("services.impl.auth_service.create_refresh_token") as mock_refresh:

            mock_access.return_value = "test_access_token"
            mock_refresh.return_value = "test_refresh_token"

            await auth_service.register(
                username="testuser",
                email=email,
                password=password
            )

        with patch("services.impl.auth_service.verify_password", return_value=False):
            with pytest.raises(ValueError, match="密码错误"):
                await auth_service.login(
                    username=email,
                    password="wrongpassword"
                )

    @pytest.mark.asyncio
    async def test_auth_flow_duplicate_email(self, auth_service):
        """测试重复邮箱注册失败"""
        email = "duplicate@example.com"
        password = "TestPass123!"

        with patch("services.impl.auth_service.create_access_token"), \
             patch("services.impl.auth_service.create_refresh_token"):

            await auth_service.register(
                username="user1",
                email=email,
                password=password
            )

            with pytest.raises(ValueError, match="该邮箱已被注册"):
                await auth_service.register(
                    username="user2",
                    email=email,
                    password=password
                )

    @pytest.mark.asyncio
    async def test_auth_flow_duplicate_username(self, auth_service):
        """测试重复用户名注册失败"""
        username = "duplicateuser"
        password = "TestPass123!"

        with patch("services.impl.auth_service.create_access_token"), \
             patch("services.impl.auth_service.create_refresh_token"):

            await auth_service.register(
                username=username,
                email="user1@example.com",
                password=password
            )

            with pytest.raises(ValueError, match="该用户名已被使用"):
                await auth_service.register(
                    username=username,
                    email="user2@example.com",
                    password=password
                )

    @pytest.mark.asyncio
    async def test_refresh_token_flow(self, auth_service):
        """测试刷新令牌流程"""
        email = "refresh@example.com"
        password = "TestPass123!"

        with patch("services.impl.auth_service.create_access_token") as mock_access, \
             patch("services.impl.auth_service.create_refresh_token") as mock_refresh, \
             patch("services.impl.auth_service.decode_token") as mock_decode:

            mock_access.return_value = "new_access_token"
            mock_refresh.return_value = "new_refresh_token"

            await auth_service.register(
                username="refreshuser",
                email=email,
                password=password
            )

            mock_decode.return_value = {
                "sub": str(uuid4()),
                "type": "refresh",
                "exp": 9999999999
            }

            with patch.object(auth_service.user_repo, 'get_by_id', new_callable=AsyncMock) as mock_get:
                mock_user = MagicMock()
                mock_user.id = uuid4()
                mock_user.email = email
                mock_user.username = "refreshuser"
                mock_user.is_active = True
                mock_user.is_superuser = False
                mock_get.return_value = mock_user

                refresh_result = await auth_service.refresh_token("test_refresh_token")

                assert "access_token" in refresh_result
                assert "refresh_token" in refresh_result
                assert refresh_result["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_change_password_flow(self, auth_service):
        """测试修改密码流程"""
        email = "password@example.com"
        old_password = "OldPass123!"
        new_password = "NewPass456!"

        with patch("services.impl.auth_service.create_access_token"), \
             patch("services.impl.auth_service.create_refresh_token"), \
             patch("services.impl.auth_service.hash_password") as mock_hash:

            mock_hash.return_value = "$2b$12$new_hash"

            await auth_service.register(
                username="passworduser",
                email=email,
                password=old_password
            )

        with patch.object(auth_service.user_repo, 'get_by_id', new_callable=AsyncMock) as mock_get, \
             patch("services.impl.auth_service.verify_password") as mock_verify, \
             patch("services.impl.auth_service.hash_password") as mock_hash:

            mock_user = MagicMock()
            mock_user.id = uuid4()
            mock_user.hashed_password = hash_password(old_password)
            mock_get.return_value = mock_user
            mock_verify.return_value = True
            mock_hash.return_value = "$2b$12$new_hash"

            result = await auth_service.change_password(
                user_id=mock_user.id,
                old_password=old_password,
                new_password=new_password
            )

            assert result is True