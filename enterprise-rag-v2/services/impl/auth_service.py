"""
认证服务实现
包含登录失败锁定、审计日志集成
"""

from typing import Optional, Dict, Any
from uuid import UUID
from datetime import timezone, datetime, timedelta
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import (
    User,
    Tenant,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
    SubscriptionPlan,
    TenantStatus,
    _coerce_workspace_role,
)
from infrastructure.repositories.user_repository import UserRepositoryImpl
from services.interfaces.auth_service import AuthService
from services.utils.jwt import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    validate_password_strength,
    TokenPayload
)
from services.audit.service import AuditService, AuditAction
from infrastructure.cache.redis import RedisCache, CacheKeys
from core.config import get_settings


settings = get_settings()


class AuthServiceImpl(AuthService):
    """认证服务实现"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepositoryImpl(session)
        self.audit_service = AuditService(session)
        self.cache = RedisCache()

    async def _check_is_tenant_admin(self, user_id: UUID) -> bool:
        """判断用户是否为租户管理员（任一工作空间 owner/admin）。

        不在 SQL 里用 role IN (...)：PostgreSQL 原生枚举/VARCHAR 小写/大写混存时，
        与 ORM 绑定值不一致会导致查不到行，进而误拒租户管理员。
        """
        uid = str(UUID(str(user_id)))
        result = await self.session.execute(
            select(WorkspaceMember.role).where(WorkspaceMember.user_id == uid)
        )
        for (role_val,) in result.all():
            try:
                coerced = _coerce_workspace_role(role_val)
            except (ValueError, TypeError, AttributeError):
                continue
            if coerced in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
                return True
        return False

    async def _is_account_locked(self, user_id: UUID) -> bool:
        """检查账户是否被锁定"""
        key = f"lockout:user:{user_id}"
        return await self.cache.exists(key)

    async def _lock_account(self, user_id: UUID, minutes: int = 15) -> None:
        """锁定账户"""
        key = f"lockout:user:{user_id}"
        await self.cache.set(key, {"locked_at": datetime.now(timezone.utc).isoformat()}, ttl=minutes * 60)

    async def _unlock_account(self, user_id: UUID) -> None:
        """解锁账户"""
        key = f"lockout:user:{user_id}"
        await self.cache.delete(key)

    async def _record_failed_attempt(self, identifier: str, user_id: Optional[UUID] = None) -> int:
        """记录失败尝试次数，返回当前失败次数"""
        key = f"failed_attempts:{identifier}"
        attempts = await self.cache.get(key)
        count = (attempts or 0) + 1
        await self.cache.set(key, count, ttl=settings.security.login_lockout_minutes * 60)
        return count

    async def _clear_failed_attempts(self, identifier: str) -> None:
        """清除失败尝试记录"""
        key = f"failed_attempts:{identifier}"
        await self.cache.delete(key)

    async def _get_failed_attempts(self, identifier: str) -> int:
        """获取失败尝试次数"""
        key = f"failed_attempts:{identifier}"
        attempts = await self.cache.get(key)
        return attempts or 0

    async def register(
        self,
        username: str,
        email: str,
        password: str,
        tenant_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> dict:
        """用户注册"""
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            raise ValueError(f"密码不符合要求: {error_msg}")

        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            raise ValueError("该邮箱已被注册")

        existing_username = await self.user_repo.get_by_username(username)
        if existing_username:
            raise ValueError("该用户名已被使用")

        hashed_pw = hash_password(password)
        created_new_tenant = False

        # 自助注册默认创建独立租户，并将注册人设置为该租户管理员（OWNER）
        if not tenant_id:
            existing_tenant = await self.session.execute(
                select(Tenant).where(Tenant.contact_email == email)
            )
            if existing_tenant.scalar_one_or_none():
                raise ValueError("该邮箱已被租户占用")

            tenant_name = username.strip() or email.split("@")[0]
            created_tenant = Tenant(
                name=tenant_name,
                contact_email=email,
                plan=SubscriptionPlan.FREE,
                status=TenantStatus.ACTIVE,
                extra_metadata={"created_from": "self_register"},
            )
            self.session.add(created_tenant)
            await self.session.flush()
            tenant_id = created_tenant.id
            created_new_tenant = True

        user = User(
            username=username,
            email=email,
            hashed_password=hashed_pw,
            tenant_id=str(tenant_id) if tenant_id else None
        )

        created_user = await self.user_repo.create(user)

        if created_new_tenant and tenant_id:
            created_workspace = Workspace(
                tenant_id=str(tenant_id),
                name="默认工作空间",
                description="注册时自动创建",
                is_default=True,
                extra_metadata={"created_from": "self_register"},
            )
            self.session.add(created_workspace)
            await self.session.flush()

            self.session.add(
                WorkspaceMember(
                    workspace_id=created_workspace.id,
                    user_id=str(created_user.id),
                    role=WorkspaceRole.OWNER,
                )
            )
            created_user.current_workspace_id = created_workspace.id
            await self.session.flush()

        await self.audit_service.log(
            action=AuditAction.USER_CREATE,
            tenant_id=str(tenant_id) if tenant_id else None,
            user_id=str(created_user.id),
            resource_type="user",
            resource_id=str(created_user.id),
            details={"username": username, "email": email},
            ip_address=ip_address,
            user_agent=user_agent
        )

        # 自动加入公共工作空间（同租户内所有用户自动可读）
        if tenant_id:
            from services.impl.workspace_service import get_public_workspaces_for_tenant

            public_workspaces = await get_public_workspaces_for_tenant(
                self.session, str(tenant_id)
            )
            for pw in public_workspaces:
                # 检查是否已是成员（避免重复）
                existing_member = await self.session.execute(
                    select(WorkspaceMember).where(
                        WorkspaceMember.workspace_id == pw.id,
                        WorkspaceMember.user_id == str(created_user.id),
                    )
                )
                if not existing_member.scalar_one_or_none():
                    self.session.add(
                        WorkspaceMember(
                            workspace_id=pw.id,
                            user_id=str(created_user.id),
                            role=WorkspaceRole.VIEWER,
                        )
                    )
            if public_workspaces:
                await self.session.flush()

        access_token = create_access_token({
            "sub": str(created_user.id),
            "username": created_user.username,
            "email": created_user.email,
            "tenant_id": str(tenant_id) if tenant_id else None,
            "is_superuser": created_user.is_superuser,
            "is_tenant_admin": created_new_tenant,
        })

        refresh_token = create_refresh_token({
            "sub": str(created_user.id)
        })

        return {
            "user": {
                "id": str(created_user.id),
                "name": created_user.username,
                "username": created_user.username,
                "email": created_user.email,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "current_workspace_id": str(created_user.current_workspace_id) if created_user.current_workspace_id else None,
                "is_active": created_user.is_active,
                "is_superuser": created_user.is_superuser,
                "is_tenant_admin": created_new_tenant,
                "created_at": created_user.created_at.isoformat() if created_user.created_at else None,
                "updated_at": created_user.updated_at.isoformat() if created_user.updated_at else None
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    async def login(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> dict:
        """用户登录"""
        user = await self.user_repo.get_by_username(username)
        if not user:
            user = await self.user_repo.get_by_email(username)

        if not user:
            await self._record_failed_attempt(ip_address)
            await self.audit_service.log_login(
                user_id=None,
                tenant_id=None,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message="用户不存在",
                username=username
            )
            raise ValueError("用户不存在")

        if await self._is_account_locked(user.id):
            await self.audit_service.log_login(
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message="账户已被锁定",
                username=username
            )
            raise ValueError("账户已被锁定，请稍后再试")

        if not verify_password(password, user.hashed_password):
            failed_count = await self._record_failed_attempt(str(user.id), user.id)
            
            await self.audit_service.log_login(
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message=f"密码错误 (尝试 {failed_count}/{settings.security.login_max_attempts})",
                username=username
            )

            if failed_count >= settings.security.login_max_attempts:
                await self._lock_account(user.id, settings.security.login_lockout_minutes)
                await self.audit_service.log_account_locked(
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                    ip_address=ip_address,
                    reason="too_many_failed_attempts"
                )
                raise ValueError(f"登录失败次数过多，账户已锁定 {settings.security.login_lockout_minutes} 分钟")

            raise ValueError(f"密码错误，还剩 {settings.security.login_max_attempts - failed_count} 次尝试机会")

        if not user.is_active:
            await self.audit_service.log_login(
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message="用户已被禁用",
                username=username
            )
            raise ValueError("用户已被禁用")

        await self._clear_failed_attempts(str(user.id))
        await self._clear_failed_attempts(ip_address)
        await self._unlock_account(user.id)

        await self.audit_service.log_login(
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip_address=ip_address,
            user_agent=user_agent,
            success=True,
            username=username
        )

        is_tenant_admin = await self._check_is_tenant_admin(user.id)

        access_token = create_access_token({
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "is_superuser": user.is_superuser,
            "is_tenant_admin": is_tenant_admin,
        })

        refresh_token = create_refresh_token({
            "sub": str(user.id)
        })

        return {
            "user": {
                "id": str(user.id),
                "name": user.username,
                "username": user.username,
                "email": user.email,
                "tenant_id": str(user.tenant_id) if user.tenant_id else None,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "is_tenant_admin": is_tenant_admin,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    async def refresh_token(self, refresh_token: str) -> dict:
        """刷新访问令牌"""
        payload = decode_token(refresh_token)
        if not payload:
            raise ValueError("无效的刷新令牌")

        if payload.get("type") != "refresh":
            raise ValueError("不是刷新令牌")

        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("令牌格式错误")

        user = await self.user_repo.get_by_id(UUID(user_id))
        if not user:
            raise ValueError("用户不存在")

        if not user.is_active:
            raise ValueError("用户已被禁用")

        is_tenant_admin = await self._check_is_tenant_admin(user.id)

        new_access_token = create_access_token({
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "is_superuser": user.is_superuser,
            "is_tenant_admin": is_tenant_admin,
        })

        new_refresh_token = create_refresh_token({
            "sub": str(user.id)
        })

        await self.audit_service.log(
            action=AuditAction.TOKEN_REFRESH,
            user_id=user.id,
            tenant_id=user.tenant_id,
            resource_type="user",
            resource_id=str(user.id)
        )

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }

    async def logout(
        self,
        user_id: UUID,
        access_token: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """用户登出"""
        user = await self.user_repo.get_by_id(user_id)
        if user:
            await self.audit_service.log_logout(
                user_id=user_id,
                tenant_id=user.tenant_id,
                ip_address=ip_address
            )
        
        token_blacklist_key = f"blacklist:token:{access_token}"
        await self.cache.set(token_blacklist_key, {"revoked_at": datetime.now(timezone.utc).isoformat()}, ttl=3600)
        
        return True

    async def verify_token(self, token: str) -> Optional[dict]:
        """验证令牌"""
        blacklist_key = f"blacklist:token:{token}"
        if await self.cache.exists(blacklist_key):
            return None

        payload = decode_token(token)
        if not payload:
            return None

        if payload.get("type") != "access":
            return None

        token_payload = TokenPayload(payload)

        if token_payload.is_expired:
            return None

        result = {
            "sub": token_payload.sub,
            "username": token_payload.username,
            "email": token_payload.email,
            "tenant_id": token_payload.tenant_id,
            "workspace_id": token_payload.workspace_id,
            "is_superuser": token_payload.is_superuser
        }
        # 规范 tenant_id 为合法 UUID 字符串；非法则置空以便走下方用户表补全
        tid = result.get("tenant_id")
        if tid is not None:
            try:
                from uuid import UUID as _UUID
                result["tenant_id"] = str(_UUID(str(tid).strip()))
            except (ValueError, TypeError, AttributeError):
                result["tenant_id"] = None
        # 历史 JWT 可能不含 tenant_id，从用户表补全，避免工作区/用户列表等依赖租户的接口异常
        if not result.get("tenant_id") and token_payload.sub:
            try:
                user = await self.user_repo.get_by_id(UUID(str(token_payload.sub)))
                if user and getattr(user, "tenant_id", None):
                    result["tenant_id"] = str(user.tenant_id)
            except (ValueError, TypeError):
                pass
        return result

    async def change_password(
        self,
        user_id: UUID,
        old_password: str,
        new_password: str,
        ip_address: Optional[str] = None
    ) -> bool:
        """修改密码"""
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(f"新密码不符合要求: {error_msg}")

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("用户不存在")

        if not verify_password(old_password, user.hashed_password):
            raise ValueError("旧密码错误")

        user.hashed_password = hash_password(new_password)
        await self.user_repo.update(user)

        await self.audit_service.log(
            action=AuditAction.PASSWORD_CHANGE,
            user_id=user_id,
            tenant_id=user.tenant_id,
            resource_type="user",
            resource_id=str(user_id),
            ip_address=ip_address
        )

        return True

    async def reset_password(self, email: str) -> bool:
        """重置密码"""
        return True

    async def verify_permission(
        self,
        user_id: UUID,
        resource_type: str,
        resource_id: UUID,
        action: str
    ) -> bool:
        """验证权限"""
        from infrastructure.database.models import (
            Workspace, WorkspaceMember, WorkspaceRole,
            Dataset, Document
        )
        from sqlalchemy import select

        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return False

        if user.is_superuser:
            return True

        workspace_id = None

        # 根据资源类型查找对应的工作空间ID
        if resource_type == "workspace":
            workspace_id = resource_id
        elif resource_type == "dataset":
            result = await self.session.execute(
                select(Dataset).where(Dataset.id == str(resource_id))
            )
            dataset = result.scalar_one_or_none()
            if dataset:
                workspace_id = UUID(dataset.workspace_id)
        elif resource_type == "document":
            result = await self.session.execute(
                select(Document).where(Document.id == str(resource_id))
            )
            document = result.scalar_one_or_none()
            if document:
                dataset_result = await self.session.execute(
                    select(Dataset).where(Dataset.id == str(document.dataset_id))
                )
                dataset = dataset_result.scalar_one_or_none()
                if dataset:
                    workspace_id = UUID(dataset.workspace_id)

        if not workspace_id:
            return False

        # 查询用户在该工作空间中的角色
        result = await self.session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == str(workspace_id),
                WorkspaceMember.user_id == str(user_id)
            )
        )
        member = result.scalar_one_or_none()

        if not member:
            return False

        # 兼容数据库返回 Enum / "ADMIN" / "admin" 三种形式
        role_raw = member.role
        if isinstance(role_raw, WorkspaceRole):
            role_key = role_raw.value
        elif isinstance(role_raw, str):
            role_key = role_raw.lower()
        else:
            role_key = str(role_raw).lower()

        # 角色权限映射
        # 权限层级: OWNER > ADMIN > MEMBER > VIEWER
        role_permissions = {
            "owner": ["view", "edit", "delete", "manage_members"],
            "admin": ["view", "edit", "delete", "manage_members"],
            "member": ["view", "edit", "delete"],
            "viewer": ["view"]
        }

        # 检查动作是否在该角色的权限列表中
        allowed_actions = role_permissions.get(role_key, [])
        return action in allowed_actions
