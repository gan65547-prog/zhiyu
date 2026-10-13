"""
API路由层测试 - 认证路由

测试认证相关的API端点
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch


class TestAuthRouter:
    """认证路由测试"""

    @pytest.fixture
    def mock_auth_service(self):
        service = MagicMock()
        service.register = AsyncMock(return_value={
            "user": {"id": str(uuid4()), "email": "test@example.com", "username": "testuser"},
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_type": "bearer"
        })
        service.login = AsyncMock(return_value={
            "user": {"id": str(uuid4()), "email": "test@example.com"},
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_type": "bearer"
        })
        service.refresh_token = AsyncMock(return_value={
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "token_type": "bearer"
        })
        service.logout = AsyncMock(return_value=True)
        service.change_password = AsyncMock(return_value=True)
        return service

    @pytest.mark.asyncio
    async def test_register_success(self, mock_auth_service):
        """测试注册成功"""
        result = await mock_auth_service.register(
            username="testuser",
            email="test@example.com",
            password="TestPass123!"
        )

        assert result["user"]["email"] == "test@example.com"
        assert result["access_token"] == "test_access_token"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, mock_auth_service):
        """测试重复邮箱注册失败"""
        mock_auth_service.register = AsyncMock(side_effect=ValueError("该邮箱已被注册"))

        with pytest.raises(ValueError, match="该邮箱已被注册"):
            await mock_auth_service.register(
                username="testuser",
                email="test@example.com",
                password="TestPass123!"
            )

    @pytest.mark.asyncio
    async def test_login_success(self, mock_auth_service):
        """测试登录成功"""
        result = await mock_auth_service.login(
            username="test@example.com",
            password="TestPass123!"
        )

        assert result["access_token"] == "test_access_token"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, mock_auth_service):
        """测试登录失败"""
        mock_auth_service.login = AsyncMock(side_effect=ValueError("密码错误"))

        with pytest.raises(ValueError, match="密码错误"):
            await mock_auth_service.login(
                username="test@example.com",
                password="wrongpassword"
            )

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, mock_auth_service):
        """测试刷新Token成功"""
        result = await mock_auth_service.refresh_token("valid_refresh_token")

        assert result["access_token"] == "new_access_token"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, mock_auth_service):
        """测试刷新Token失败"""
        mock_auth_service.refresh_token = AsyncMock(side_effect=ValueError("Invalid refresh token"))

        with pytest.raises(ValueError, match="Invalid refresh token"):
            await mock_auth_service.refresh_token("invalid_token")

    @pytest.mark.asyncio
    async def test_logout_success(self, mock_auth_service):
        """测试登出成功"""
        result = await mock_auth_service.logout(user_id=uuid4(), access_token="access_token")

        assert result is True

    @pytest.mark.asyncio
    async def test_change_password_success(self, mock_auth_service):
        """测试修改密码成功"""
        result = await mock_auth_service.change_password(
            user_id=uuid4(),
            old_password="OldPass123!",
            new_password="NewPass456!"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self, mock_auth_service):
        """测试旧密码错误"""
        mock_auth_service.change_password = AsyncMock(side_effect=ValueError("旧密码错误"))

        with pytest.raises(ValueError, match="旧密码错误"):
            await mock_auth_service.change_password(
                user_id=uuid4(),
                old_password="wrongpassword",
                new_password="NewPass456!"
            )
