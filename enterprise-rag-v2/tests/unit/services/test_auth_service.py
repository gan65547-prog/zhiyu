"""
单元测试 - 认证服务
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.impl.auth_service import AuthServiceImpl
from infrastructure.database.models import User, WorkspaceRole
from services.utils.jwt import hash_password


class TestAuthServiceImpl:
    """AuthServiceImpl单元测试"""

    @pytest.fixture
    def mock_session(self):
        """创建模拟数据库会话（execute 可安全 await，all/scalars 为空）"""
        session = MagicMock()
        result = MagicMock()
        result.all.return_value = []
        result.scalars.return_value.all.return_value = []
        result.scalar_one_or_none.return_value = None
        result.first.return_value = None
        session.execute = AsyncMock(return_value=result)
        session.flush = AsyncMock()
        session.add = MagicMock()
        session.get = AsyncMock(return_value=None)
        return session

    @pytest.fixture
    def auth_service(self, mock_session):
        """创建AuthServiceImpl实例，并打桩缓存/审计/租户管理员判定，避免依赖真实 Redis 与复杂 SQL mock。"""
        svc = AuthServiceImpl(session=mock_session)
        svc.cache.exists = AsyncMock(return_value=False)
        svc.cache.get = AsyncMock(return_value=None)
        svc.cache.set = AsyncMock()
        svc.cache.delete = AsyncMock()
        svc.audit_service.log = AsyncMock(return_value=None)
        svc.audit_service.log_login = AsyncMock(return_value=None)
        svc.audit_service.log_account_locked = AsyncMock(return_value=None)
        svc.audit_service.log_logout = AsyncMock(return_value=None)
        svc._check_is_tenant_admin = AsyncMock(return_value=False)
        return svc

    @pytest.mark.asyncio
    async def test_register_success(self, auth_service, valid_password):
        """测试成功注册"""
        with patch.object(auth_service.user_repo, 'get_by_email', new_callable=AsyncMock) as mock_get_email, \
             patch.object(auth_service.user_repo, 'get_by_username', new_callable=AsyncMock) as mock_get_username, \
             patch.object(auth_service.user_repo, 'create', new_callable=AsyncMock) as mock_create:

            mock_get_email.return_value = None
            mock_get_username.return_value = None

            user_id = uuid4()
            tenant_id = uuid4()
            mock_user = User(
                id=user_id,
                username="newuser",
                email="new@example.com",
                hashed_password=hash_password(valid_password),
                is_active=True,
                tenant_id=str(tenant_id)
            )
            mock_create.return_value = mock_user

            with patch("services.impl.auth_service.create_access_token") as mock_access_token, \
                 patch("services.impl.auth_service.create_refresh_token") as mock_refresh_token:

                mock_access_token.return_value = "access_token_123"
                mock_refresh_token.return_value = "refresh_token_123"

                result = await auth_service.register(
                    username="newuser",
                    email="new@example.com",
                    password=valid_password,
                    tenant_id=tenant_id
                )

                assert "user" in result
                assert "access_token" in result
                assert "refresh_token" in result
                assert "token_type" in result
                assert result["token_type"] == "bearer"
                assert result["user"]["username"] == "newuser"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, auth_service, valid_password):
        """测试重复邮箱注册失败"""
        with patch.object(auth_service.user_repo, 'get_by_email', new_callable=AsyncMock) as mock_get_email:
            existing_user = User(
                id=uuid4(),
                username="existing",
                email="existing@example.com",
                hashed_password="hash",
                is_active=True,
                tenant_id=None
            )
            mock_get_email.return_value = existing_user

            with pytest.raises(ValueError, match="该邮箱已被注册"):
                await auth_service.register(
                    username="newuser",
                    email="existing@example.com",
                    password=valid_password
                )

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, auth_service, valid_password):
        """测试重复用户名注册失败"""
        with patch.object(auth_service.user_repo, 'get_by_email', new_callable=AsyncMock) as mock_get_email, \
             patch.object(auth_service.user_repo, 'get_by_username', new_callable=AsyncMock) as mock_get_username:

            mock_get_email.return_value = None
            mock_get_username.return_value = User(
                id=uuid4(),
                username="existing",
                email="existing@example.com",
                hashed_password="hash",
                is_active=True,
                tenant_id=None
            )

            with pytest.raises(ValueError, match="该用户名已被使用"):
                await auth_service.register(
                    username="existing",
                    email="new@example.com",
                    password=valid_password
                )

    @pytest.mark.asyncio
    async def test_register_weak_password(self, auth_service, weak_password):
        """测试弱密码注册失败"""
        with pytest.raises(ValueError, match="密码不符合要求"):
            await auth_service.register(
                username="newuser",
                email="new@example.com",
                password=weak_password
            )

    @pytest.mark.asyncio
    async def test_register_password_without_uppercase(self, auth_service, password_without_uppercase):
        """测试缺少大写字母的密码注册失败"""
        with pytest.raises(ValueError, match="密码不符合要求"):
            await auth_service.register(
                username="newuser",
                email="new@example.com",
                password=password_without_uppercase
            )

    @pytest.mark.asyncio
    async def test_login_success(self, auth_service, valid_password):
        """测试成功登录"""
        with patch.object(auth_service.user_repo, 'get_by_username', new_callable=AsyncMock) as mock_get_username, \
             patch("services.impl.auth_service.verify_password") as mock_verify, \
             patch("services.impl.auth_service.create_access_token") as mock_access_token, \
             patch("services.impl.auth_service.create_refresh_token") as mock_refresh_token:

            user_id = uuid4()
            mock_user = User(
                id=user_id,
                username="testuser",
                email="test@example.com",
                hashed_password=hash_password(valid_password),
                is_active=True,
                tenant_id=None
            )
            mock_get_username.return_value = mock_user
            mock_verify.return_value = True
            mock_access_token.return_value = "access_token_123"
            mock_refresh_token.return_value = "refresh_token_123"

            result = await auth_service.login(
                username="testuser",
                password=valid_password
            )

            assert "user" in result
            assert "access_token" in result
            assert "refresh_token" in result
            assert "token_type" in result
            assert result["user"]["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_login_user_not_found(self, auth_service, valid_password):
        """测试用户不存在登录失败"""
        with patch.object(auth_service.user_repo, 'get_by_username', new_callable=AsyncMock) as mock_get_username, \
             patch.object(auth_service.user_repo, 'get_by_email', new_callable=AsyncMock) as mock_get_email:

            mock_get_username.return_value = None
            mock_get_email.return_value = None

            with pytest.raises(ValueError, match="用户不存在"):
                await auth_service.login(
                    username="nonexistent",
                    password=valid_password
                )

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, auth_service, valid_password):
        """测试密码错误登录失败"""
        with patch.object(auth_service.user_repo, 'get_by_username', new_callable=AsyncMock) as mock_get_username, \
             patch("services.impl.auth_service.verify_password") as mock_verify:

            user_id = uuid4()
            mock_user = User(
                id=user_id,
                username="testuser",
                email="test@example.com",
                hashed_password=hash_password(valid_password),
                is_active=True,
                tenant_id=None
            )
            mock_get_username.return_value = mock_user
            mock_verify.return_value = False

            with pytest.raises(ValueError, match="密码错误"):
                await auth_service.login(
                    username="testuser",
                    password="wrongpassword"
                )

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, auth_service, valid_password):
        """测试禁用用户登录失败"""
        with patch.object(auth_service.user_repo, 'get_by_username', new_callable=AsyncMock) as mock_get_username, \
             patch("services.impl.auth_service.verify_password") as mock_verify:

            user_id = uuid4()
            mock_user = User(
                id=user_id,
                username="testuser",
                email="test@example.com",
                hashed_password=hash_password(valid_password),
                is_active=False,
                tenant_id=None
            )
            mock_get_username.return_value = mock_user
            mock_verify.return_value = True

            with pytest.raises(ValueError, match="用户已被禁用"):
                await auth_service.login(
                    username="testuser",
                    password=valid_password
                )

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, auth_service):
        """测试成功刷新令牌"""
        with patch("services.impl.auth_service.decode_token") as mock_decode, \
             patch.object(auth_service.user_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id, \
             patch("services.impl.auth_service.create_access_token") as mock_access_token, \
             patch("services.impl.auth_service.create_refresh_token") as mock_refresh_token:

            user_id = uuid4()
            mock_decode.return_value = {
                "sub": str(user_id),
                "type": "refresh",
                "exp": 9999999999
            }
            mock_user = User(
                id=user_id,
                username="testuser",
                email="test@example.com",
                hashed_password="hash",
                is_active=True,
                tenant_id=None
            )
            mock_get_by_id.return_value = mock_user
            mock_access_token.return_value = "new_access_token"
            mock_refresh_token.return_value = "new_refresh_token"

            result = await auth_service.refresh_token("valid_refresh_token")

            assert "access_token" in result
            assert "refresh_token" in result
            assert result["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, auth_service):
        """测试无效刷新令牌"""
        with patch("services.impl.auth_service.decode_token") as mock_decode:
            mock_decode.return_value = None

            with pytest.raises(ValueError, match="无效的刷新令牌"):
                await auth_service.refresh_token("invalid_token")

    @pytest.mark.asyncio
    async def test_refresh_token_wrong_type(self, auth_service):
        """测试错误类型的令牌"""
        with patch("services.impl.auth_service.decode_token") as mock_decode:
            mock_decode.return_value = {
                "sub": str(uuid4()),
                "type": "access",
                "exp": 9999999999
            }

            with pytest.raises(ValueError, match="不是刷新令牌"):
                await auth_service.refresh_token("access_token")

    @pytest.mark.asyncio
    async def test_verify_token_success(self, auth_service):
        """测试验证有效令牌"""
        with patch("services.impl.auth_service.decode_token") as mock_decode:
            user_id = uuid4()
            mock_decode.return_value = {
                "sub": str(user_id),
                "username": "testuser",
                "email": "test@example.com",
                "type": "access",
                "exp": 9999999999
            }

            result = await auth_service.verify_token("valid_token")

            assert result is not None
            assert result["sub"] == str(user_id)
            assert result["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_verify_token_expired(self, auth_service):
        """测试验证过期令牌"""
        with patch("services.impl.auth_service.decode_token") as mock_decode, \
             patch("services.impl.auth_service.TokenPayload") as mock_payload:

            mock_decode.return_value = {
                "sub": str(uuid4()),
                "type": "access",
                "exp": 0
            }
            mock_payload_instance = MagicMock()
            mock_payload_instance.is_expired = True
            mock_payload.return_value = mock_payload_instance

            result = await auth_service.verify_token("expired_token")

            assert result is None

    @pytest.mark.asyncio
    async def test_change_password_success(self, auth_service, valid_password):
        """测试成功修改密码"""
        with patch.object(auth_service.user_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id, \
             patch("services.impl.auth_service.verify_password") as mock_verify, \
             patch.object(auth_service.user_repo, 'update', new_callable=AsyncMock) as mock_update, \
             patch("services.impl.auth_service.hash_password") as mock_hash:

            user_id = uuid4()
            mock_user = MagicMock()
            mock_user.id = user_id
            mock_user.hashed_password = "old_hash"
            mock_get_by_id.return_value = mock_user
            mock_verify.return_value = True
            mock_hash.return_value = "new_hash"
            mock_update.return_value = mock_user

            result = await auth_service.change_password(
                user_id=user_id,
                old_password=valid_password,
                new_password="NewPass456!"
            )

            assert result is True
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_change_password_wrong_old(self, auth_service, valid_password):
        """测试旧密码错误修改密码失败"""
        with patch.object(auth_service.user_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id, \
             patch("services.impl.auth_service.verify_password") as mock_verify:

            user_id = uuid4()
            mock_user = MagicMock()
            mock_user.id = user_id
            mock_user.hashed_password = "old_hash"
            mock_get_by_id.return_value = mock_user
            mock_verify.return_value = False

            with pytest.raises(ValueError, match="旧密码错误"):
                await auth_service.change_password(
                    user_id=user_id,
                    old_password="wrong_old_password",
                    new_password="NewPass456!"
                )

    @pytest.mark.asyncio
    async def test_change_password_weak_new(self, auth_service, valid_password):
        """测试新密码太弱修改密码失败"""
        with patch.object(auth_service.user_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id, \
             patch("services.impl.auth_service.verify_password") as mock_verify:

            user_id = uuid4()
            mock_user = MagicMock()
            mock_user.id = user_id
            mock_user.hashed_password = "old_hash"
            mock_get_by_id.return_value = mock_user
            mock_verify.return_value = True

            with pytest.raises(ValueError, match="新密码不符合要求"):
                await auth_service.change_password(
                    user_id=user_id,
                    old_password=valid_password,
                    new_password="weak"
                )

    @pytest.mark.asyncio
    async def test_verify_permission_superuser(self, auth_service):
        """测试超级用户权限验证"""
        with patch.object(auth_service.user_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            user_id = uuid4()
            mock_user = User(
                id=user_id,
                username="admin",
                email="admin@example.com",
                hashed_password="hash",
                is_active=True,
                is_superuser=True,
                tenant_id=None
            )
            mock_get_by_id.return_value = mock_user

            result = await auth_service.verify_permission(
                user_id=user_id,
                resource_type="workspace",
                resource_id=uuid4(),
                action="delete"
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_verify_permission_regular_user(self, auth_service):
        """测试普通用户权限验证"""
        with patch.object(auth_service.user_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            user_id = uuid4()
            mock_user = User(
                id=user_id,
                username="user",
                email="user@example.com",
                hashed_password="hash",
                is_active=True,
                is_superuser=False,
                tenant_id=None
            )
            mock_get_by_id.return_value = mock_user

            member = MagicMock()
            member.role = WorkspaceRole.OWNER
            res = MagicMock()
            res.scalar_one_or_none.return_value = member
            auth_service.session.execute = AsyncMock(return_value=res)

            result = await auth_service.verify_permission(
                user_id=user_id,
                resource_type="workspace",
                resource_id=uuid4(),
                action="delete"
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_verify_permission_user_not_found(self, auth_service):
        """测试用户不存在时的权限验证"""
        with patch.object(auth_service.user_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_by_id:
            mock_get_by_id.return_value = None

            result = await auth_service.verify_permission(
                user_id=uuid4(),
                resource_type="workspace",
                resource_id=uuid4(),
                action="delete"
            )

            assert result is False


class TestPasswordValidation:
    """密码强度验证测试"""

    def test_valid_password(self, valid_password):
        """测试有效密码"""
        from services.utils.jwt import validate_password_strength
        is_valid, _ = validate_password_strength(valid_password)
        assert is_valid is True

    def test_short_password(self):
        """测试太短的密码"""
        from services.utils.jwt import validate_password_strength
        is_valid, error_msg = validate_password_strength("Ab1!")
        assert is_valid is False
        assert "至少8个字符" in error_msg

    def test_password_without_uppercase(self, password_without_uppercase):
        """测试没有大写字母的密码"""
        from services.utils.jwt import validate_password_strength
        is_valid, error_msg = validate_password_strength(password_without_uppercase)
        assert is_valid is False
        assert "大小写字母和数字" in error_msg

    def test_password_without_lowercase(self):
        """测试没有小写字母的密码"""
        from services.utils.jwt import validate_password_strength
        is_valid, _ = validate_password_strength("TESTPASS123")
        assert is_valid is False

    def test_password_without_digit(self):
        """测试没有数字的密码"""
        from services.utils.jwt import validate_password_strength
        is_valid, _ = validate_password_strength("TestPassword")
        assert is_valid is False
