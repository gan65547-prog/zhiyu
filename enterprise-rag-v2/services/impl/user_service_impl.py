"""
用户服务实现

提供用户管理的核心业务逻辑
"""

from typing import Optional, List, Dict
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.logging.logger import get_logger

from infrastructure.database.models import (
    User, Tenant, Workspace, WorkspaceMember, WorkspaceRole,
    Conversation, AuditLog, APIKey, UserConfig, UserAPIKey, LoginActivity
)
from services.interfaces.user_service import UserService
from services.utils.jwt import hash_password
from core.value_objects.pagination import Page
from apps.commercialization.models import QuotaExceededError as CommerceQuotaExceededError
from services.permission_checker import PermissionChecker
from core.exceptions import (
    ResourceNotFoundError,
    PermissionDeniedError,
    BusinessError,
    ValidationError,
    ResourceConflictError,
)


class UserServiceImpl(UserService):
    """用户服务实现"""
    
    def __init__(self, db: AsyncSession, quota_service=None):
        self.db = db
        self._quota_service = quota_service
        self.logger = get_logger(__name__)

    async def _expand_workspace_ids_for_tenant_admin(
        self,
        tenant_id: UUID,
        workspace_ids: Optional[List[UUID]],
        default_role: str,
    ) -> Optional[List[UUID]]:
        """租户管理员（owner/admin）始终绑定租户下全部工作空间。"""
        try:
            normalized_role = WorkspaceRole(default_role) if default_role else WorkspaceRole.MEMBER
        except ValueError:
            normalized_role = WorkspaceRole.MEMBER

        if normalized_role not in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
            return workspace_ids

        result = await self.db.execute(
            select(Workspace.id).where(Workspace.tenant_id == str(tenant_id))
        )
        workspace_ids_all = [UUID(str(row[0])) for row in result.all()]
        self.logger.debug(
            "租户管理员角色自动扩展工作空间: tenant_id=%s, role=%s, count=%s",
            tenant_id,
            normalized_role.value,
            len(workspace_ids_all),
        )
        return workspace_ids_all
    
    async def list_users(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        workspace_id: Optional[UUID] = None
    ) -> Page:
        """获取租户的用户列表"""
        # 构建查询
        query = select(User).where(
            User.tenant_id == str(tenant_id),
            User.is_superuser == False,
        )
        
        # 如果指定了工作空间，过滤该工作空间的成员
        if workspace_id:
            # 先获取工作空间成员的用户ID
            member_query = select(WorkspaceMember.user_id).where(
                WorkspaceMember.workspace_id == str(workspace_id)
            )
            member_result = await self.db.execute(member_query)
            user_ids = [row[0] for row in member_result]
            if user_ids:
                query = query.where(User.id.in_(user_ids))
            else:
                return Page(items=[], total=0, page=page, page_size=page_size)
        
        # 搜索过滤
        if search:
            query = query.where(
                or_(
                    User.username.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )
        
        # 状态过滤
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        
        # 计算总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.scalar(count_query)
        if total is None:
            total = 0
        
        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        
        # 执行查询
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        # 转换为字典
        user_dicts = []
        for user in users:
            user_dict = {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "tenant_id": str(user.tenant_id),
                "current_workspace_id": str(user.current_workspace_id) if user.current_workspace_id else None,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "updated_at": user.updated_at.isoformat() if user.updated_at else None
            }
            user_dicts.append(user_dict)
        
        return Page(
            items=user_dicts,
            total=total,
            page=page,
            page_size=page_size
        )
    
    async def _check_tenant_quota(self, tenant_id: UUID):
        """检查部署者配置的租户用户资源上限。"""
        if self._quota_service:
            await self._quota_service.check_quota(str(tenant_id), "users")
            return

        tenant = await self.db.get(Tenant, str(tenant_id))
        if not tenant:
            raise ResourceNotFoundError("Tenant not found")

        count_query = select(func.count()).where(
            and_(
                User.tenant_id == str(tenant_id),
                User.is_active == True
            )
        )
        current_users = await self.db.scalar(count_query)

        max_users = -1
        if tenant.extra_metadata and "max_users" in tenant.extra_metadata:
            max_users = tenant.extra_metadata["max_users"]

        if max_users != -1 and current_users >= max_users:
            raise CommerceQuotaExceededError("users", current_users, max_users)
    
    async def create_user(
        self,
        tenant_id: UUID,
        username: str,
        email: str,
        password: str,
        is_active: bool = True,
        workspace_ids: Optional[List[UUID]] = None,
        default_role: str = "member"
    ) -> dict:
        """创建新用户"""
        self.logger.debug(f"创建用户开始: username={username}, email={email}, tenant_id={tenant_id}")
        # 1. 检查租户配额
        await self._check_tenant_quota(tenant_id)
        
        # 2. 验证租户存在
        tenant = await self.db.get(Tenant, str(tenant_id))
        if not tenant:
            self.logger.debug(f"租户不存在: tenant_id={tenant_id}")
            raise ResourceNotFoundError(f"Tenant {tenant_id} not found")
        
        # 检查用户名和邮箱唯一性
        username_query = select(User).where(User.username == username)
        username_result = await self.db.execute(username_query)
        if username_result.scalar_one_or_none():
            self.logger.debug(f"用户名已存在: {username}")
            raise ResourceConflictError("Username already exists")
        
        email_query = select(User).where(User.email == email)
        email_result = await self.db.execute(email_query)
        if email_result.scalar_one_or_none():
            self.logger.debug(f"邮箱已存在: {email}")
            raise ResourceConflictError("Email already exists")
        
        # 验证密码强度
        if len(password) < 8:
            self.logger.debug(f"密码强度不足: {len(password)} characters")
            raise ValidationError("密码长度至少8个字符")
        
        # 创建用户
        user = User(
            tenant_id=str(tenant_id),
            username=username,
            email=email,
            hashed_password=hash_password(password),
            is_active=is_active,
            is_superuser=False
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        self.logger.debug(f"用户创建成功: user_id={user.id}, username={user.username}")
        
        workspace_ids = await self._expand_workspace_ids_for_tenant_admin(
            tenant_id=tenant_id,
            workspace_ids=workspace_ids,
            default_role=default_role,
        )

        # 自动加入工作空间
        if workspace_ids:
            self.logger.debug(f"自动加入工作空间: workspace_ids={workspace_ids}, default_role={default_role}")
            for ws_id in workspace_ids:
                ws = await self.db.get(Workspace, str(ws_id))
                if ws and str(ws.tenant_id) == str(tenant_id):
                    self.logger.debug(f"添加工作空间成员: workspace_id={ws_id}, user_id={user.id}, role={default_role}")
                    # 确保角色是有效的
                    try:
                        role = WorkspaceRole(default_role)
                    except ValueError:
                        self.logger.debug(f"角色无效，使用默认角色: {default_role}")
                        role = WorkspaceRole.MEMBER
                    
                    member = WorkspaceMember(
                        workspace_id=str(ws_id),
                        user_id=str(user.id),
                        role=role
                    )
                    self.db.add(member)
            
            # 设置第一个工作空间为当前工作空间
            if workspace_ids:
                user.current_workspace_id = str(workspace_ids[0])
                await self.db.commit()
                self.logger.debug(f"设置当前工作空间: {workspace_ids[0]}")

        # 自动加入公共工作空间（同租户内所有用户自动可读）
        from services.impl.workspace_service import get_public_workspaces_for_tenant

        public_workspaces = await get_public_workspaces_for_tenant(
            self.db, str(tenant_id)
        )
        already_ws_ids = {str(ws_id) for ws_id in (workspace_ids or [])}
        for pw in public_workspaces:
            if pw.id in already_ws_ids:
                continue
            existing = await self.db.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == pw.id,
                    WorkspaceMember.user_id == str(user.id),
                )
            )
            if not existing.scalar_one_or_none():
                self.db.add(
                    WorkspaceMember(
                        workspace_id=pw.id,
                        user_id=str(user.id),
                        role=WorkspaceRole.VIEWER,
                    )
                )
        if public_workspaces:
            await self.db.commit()
            # 如果用户还没有 current_workspace，使用第一个公共工作空间
            if not user.current_workspace_id:
                user.current_workspace_id = public_workspaces[0].id
                await self.db.commit()

        # 角色信息可能被缓存，创建并授予工作空间后立即失效缓存
        await PermissionChecker.invalidate_user_cache(str(user.id))
        
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "tenant_id": str(user.tenant_id),
            "current_workspace_id": str(user.current_workspace_id) if user.current_workspace_id else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }
    
    async def get_user(
        self,
        user_id: UUID
    ) -> Optional[dict]:
        """获取用户详情"""
        user = await self.db.get(User, str(user_id))
        if not user:
            return None
        
        # 获取用户的工作空间
        ws_query = select(
            Workspace.id,
            Workspace.name,
            Workspace.is_default,
            WorkspaceMember.role,
            WorkspaceMember.joined_at
        ).join(Workspace, WorkspaceMember.workspace_id == Workspace.id).where(
            WorkspaceMember.user_id == str(user_id)
        )
        ws_result = await self.db.execute(ws_query)
        workspaces = []
        for row in ws_result:
            workspaces.append({
                "workspace_id": str(row[0]),
                "workspace_name": row[1],
                "role": row[3].value if row[3] else "member",
                "is_default": row[2],
                "joined_at": row[4].isoformat() if row[4] else None
            })
        
        # 获取租户名称
        tenant = await self.db.get(Tenant, str(user.tenant_id))
        
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "tenant_id": str(user.tenant_id),
            "tenant_name": tenant.name if tenant else None,
            "current_workspace_id": str(user.current_workspace_id) if user.current_workspace_id else None,
            "workspaces": workspaces,
            "extra_metadata": user.extra_metadata or {},
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }
    
    async def update_user(
        self,
        user_id: UUID,
        username: Optional[str] = None,
        email: Optional[str] = None,
        is_active: Optional[bool] = None,
        extra_metadata: Optional[dict] = None,
        workspace_ids: Optional[List[UUID]] = None,
        default_role: str = "member"
    ) -> dict:
        """更新用户信息"""
        self.logger.debug(f"更新用户开始: user_id={user_id}")
        user = await self.db.get(User, str(user_id))
        if not user:
            self.logger.debug(f"用户不存在: user_id={user_id}")
            raise ResourceNotFoundError(f"User {user_id} not found")
        
        self.logger.debug(f"找到用户: username={user.username}, email={user.email}, is_active={user.is_active}")
        
        # 检查用户名和邮箱唯一性
        if username and username != user.username:
            self.logger.debug(f"更新用户名: {user.username} -> {username}")
            username_query = select(User).where(
                and_(User.username == username, User.id != str(user_id))
            )
            username_result = await self.db.execute(username_query)
            if username_result.scalar_one_or_none():
                self.logger.debug(f"用户名已存在: {username}")
                raise ResourceConflictError("Username already exists")
            user.username = username
        
        if email and email != user.email:
            self.logger.debug(f"更新邮箱: {user.email} -> {email}")
            email_query = select(User).where(
                and_(User.email == email, User.id != str(user_id))
            )
            email_result = await self.db.execute(email_query)
            if email_result.scalar_one_or_none():
                self.logger.debug(f"邮箱已存在: {email}")
                raise ResourceConflictError("Email already exists")
            user.email = email
        
        # 更新其他字段
        if is_active is not None and is_active != user.is_active:
            self.logger.debug(f"更新激活状态: {user.is_active} -> {is_active}")
            user.is_active = is_active
        
        if extra_metadata:
            self.logger.debug(f"更新元数据: {extra_metadata}")
            if user.extra_metadata:
                user.extra_metadata.update(extra_metadata)
            else:
                user.extra_metadata = extra_metadata
        
        workspace_ids = await self._expand_workspace_ids_for_tenant_admin(
            tenant_id=UUID(str(user.tenant_id)),
            workspace_ids=workspace_ids,
            default_role=default_role,
        )

        # 更新工作空间权限
        if workspace_ids is not None:
            self.logger.debug(f"更新工作空间权限: workspace_ids={workspace_ids}, default_role={default_role}")
            # 先删除用户现有的所有工作空间成员关系
            delete_members_query = WorkspaceMember.__table__.delete().where(
                WorkspaceMember.user_id == str(user_id)
            )
            await self.db.execute(delete_members_query)
            self.logger.debug(f"删除用户现有的工作空间成员关系")
            
            # 然后添加新的工作空间成员关系
            if workspace_ids:
                tenant_id = user.tenant_id
                for ws_id in workspace_ids:
                    ws = await self.db.get(Workspace, str(ws_id))
                    if ws and str(ws.tenant_id) == tenant_id:
                        self.logger.debug(f"添加工作空间成员: workspace_id={ws_id}, user_id={user_id}, role={default_role}")
                        # 确保角色是有效的
                        try:
                            role = WorkspaceRole(default_role)
                        except ValueError:
                            self.logger.debug(f"角色无效，使用默认角色: {default_role}")
                            role = WorkspaceRole.MEMBER
                        
                        member = WorkspaceMember(
                            workspace_id=str(ws_id),
                            user_id=str(user_id),
                            role=role
                        )
                        self.db.add(member)
                
                # 设置第一个工作空间为当前工作空间
                if workspace_ids:
                    user.current_workspace_id = str(workspace_ids[0])
                    self.logger.debug(f"设置当前工作空间: {workspace_ids[0]}")
            else:
                # 如果没有指定工作空间，清空当前工作空间
                user.current_workspace_id = None
                self.logger.debug(f"清空当前工作空间")
        # 仅切换默认角色时（未传 workspace_ids），也应更新现有工作空间角色
        elif default_role is not None:
            self.logger.debug(f"仅更新默认角色: user_id={user_id}, default_role={default_role}")
            try:
                normalized_role = WorkspaceRole(default_role)
            except ValueError:
                self.logger.debug(f"角色无效，使用默认角色: {default_role}")
                normalized_role = WorkspaceRole.MEMBER

            members_query = select(WorkspaceMember).where(
                WorkspaceMember.user_id == str(user_id)
            )
            members_result = await self.db.execute(members_query)
            members = members_result.scalars().all()
            for member in members:
                member.role = normalized_role
        
        await self.db.commit()
        await self.db.refresh(user)
        await PermissionChecker.invalidate_user_cache(str(user_id))
        self.logger.debug(f"更新用户完成: user_id={user_id}, username={user.username}, is_active={user.is_active}")
        
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }
    
    async def delete_user(
        self,
        user_id: UUID
    ) -> bool:
        """删除用户（硬删除）"""
        self.logger.debug(f"删除用户开始: user_id={user_id}")
        user = await self.db.get(User, str(user_id))
        if not user:
            self.logger.debug(f"用户不存在: user_id={user_id}")
            raise ResourceNotFoundError(f"User {user_id} not found")
        
        self.logger.debug(f"找到用户: username={user.username}, is_active={user.is_active}")
        
        # 检查是否为工作空间的唯一OWNER
        owner_query = select(WorkspaceMember).where(
            and_(
                WorkspaceMember.user_id == str(user_id),
                WorkspaceMember.role == WorkspaceRole.OWNER.value
            )
        )
        owner_result = await self.db.execute(owner_query)
        owner_members = owner_result.scalars().all()
        
        self.logger.debug(f"用户是 {len(owner_members)} 个工作空间的所有者")
        
        for member in owner_members:
            # 检查该工作空间是否有其他OWNER
            other_owner_query = select(WorkspaceMember).where(
                and_(
                    WorkspaceMember.workspace_id == member.workspace_id,
                    WorkspaceMember.role == WorkspaceRole.OWNER.value,
                    WorkspaceMember.user_id != str(user_id)
                )
            )
            other_owner_result = await self.db.execute(other_owner_query)
            if not other_owner_result.scalar_one_or_none():
                self.logger.debug(f"用户是工作空间 {member.workspace_id} 的唯一所有者")
                raise BusinessError(
                    f"Cannot delete user: user is the only owner of workspace {member.workspace_id}. "
                    "Please transfer ownership or delete the workspace first."
                )
        
        try:
            # 硬删除用户（依赖外键的CASCADE删除）
            self.logger.debug(f"执行硬删除: 删除用户 {user.username}")
            
            # 检查关联的记录
            self.logger.debug(f"检查用户 {user_id} 的关联记录")
            
            # 检查工作空间成员记录
            workspace_members = await self.db.execute(
                select(WorkspaceMember).where(WorkspaceMember.user_id == str(user_id))
            )
            self.logger.debug(f"用户 {user_id} 有 {len(workspace_members.scalars().all())} 个工作空间成员记录")
            
            # 检查会话记录
            conversations = await self.db.execute(
                select(Conversation).where(Conversation.user_id == str(user_id))
            )
            self.logger.debug(f"用户 {user_id} 有 {len(conversations.scalars().all())} 个会话记录")
            
            # 检查审计日志记录
            audit_logs = await self.db.execute(
                select(AuditLog).where(AuditLog.user_id == str(user_id))
            )
            self.logger.debug(f"用户 {user_id} 有 {len(audit_logs.scalars().all())} 个审计日志记录")
            
            # 检查API密钥记录
            api_keys = await self.db.execute(
                select(APIKey).where(APIKey.user_id == str(user_id))
            )
            self.logger.debug(f"用户 {user_id} 有 {len(api_keys.scalars().all())} 个API密钥记录")
            
            # 检查用户配置记录
            user_configs = await self.db.execute(
                select(UserConfig).where(UserConfig.user_id == str(user_id))
            )
            self.logger.debug(f"用户 {user_id} 有 {len(user_configs.scalars().all())} 个用户配置记录")
            
            # 检查用户API密钥记录
            user_api_keys = await self.db.execute(
                select(UserAPIKey).where(UserAPIKey.user_id == str(user_id))
            )
            self.logger.debug(f"用户 {user_id} 有 {len(user_api_keys.scalars().all())} 个用户API密钥记录")
            
            # 检查登录活动记录
            login_activities = await self.db.execute(
                select(LoginActivity).where(LoginActivity.user_id == str(user_id))
            )
            self.logger.debug(f"用户 {user_id} 有 {len(login_activities.scalars().all())} 个登录活动记录")
            
            # 执行删除操作
            self.logger.debug(f"开始删除用户 {user_id}")
            await self.db.delete(user)
            self.logger.debug(f"删除操作执行完成，准备提交事务")
            
            # 提交事务
            await self.db.commit()
            self.logger.debug(f"事务提交成功，用户 {user_id} 删除完成")
            return True
        except SQLAlchemyError as e:
            self.logger.exception("删除用户失败: %s", str(e))
            await self.db.rollback()
            self.logger.debug(f"事务回滚成功")
            raise
    
    async def reset_password(
        self,
        user_id: UUID,
        new_password: str,
        send_email: bool = False
    ) -> dict:
        """重置用户密码"""
        self.logger.debug(f"重置密码开始: user_id={user_id}")
        user = await self.db.get(User, str(user_id))
        if not user:
            self.logger.debug(f"用户不存在: user_id={user_id}")
            raise ResourceNotFoundError(f"User {user_id} not found")
        
        self.logger.debug(f"找到用户: username={user.username}")
        
        # 验证密码强度
        self.logger.debug(f"验证密码强度")
        self._validate_password_strength(new_password)
        
        # 重置密码
        self.logger.debug(f"执行密码重置")
        user.hashed_password = hash_password(new_password)
        await self.db.commit()
        
        self.logger.debug(f"重置密码完成: user_id={user_id}, username={user.username}")
        
        return {
            "message": "Password reset successfully",
            "email_sent": send_email
        }
    
    async def activate_user(
        self,
        user_id: UUID,
        is_active: bool
    ) -> dict:
        """激活/停用用户"""
        self.logger.debug(f"激活/停用用户开始: user_id={user_id}, is_active={is_active}")
        user = await self.db.get(User, str(user_id))
        if not user:
            self.logger.debug(f"用户不存在: user_id={user_id}")
            raise ResourceNotFoundError(f"User {user_id} not found")
        
        self.logger.debug(f"找到用户: username={user.username}, 当前状态={user.is_active}")
        
        if user.is_active != is_active:
            self.logger.debug(f"更新激活状态: {user.is_active} -> {is_active}")
            user.is_active = is_active
            await self.db.commit()
            await self.db.refresh(user)
            self.logger.debug(f"激活/停用用户完成: user_id={user_id}, is_active={user.is_active}")
        else:
            self.logger.debug(f"激活状态未改变: {user.is_active}")
        
        return {
            "id": str(user.id),
            "is_active": user.is_active,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None
        }
    
    async def get_user_workspaces(
        self,
        user_id: UUID
    ) -> List[dict]:
        """获取用户的工作空间列表"""
        query = select(
            Workspace.id,
            Workspace.name,
            Workspace.is_default,
            WorkspaceMember.role,
            WorkspaceMember.joined_at
        ).join(Workspace, WorkspaceMember.workspace_id == Workspace.id).where(
            WorkspaceMember.user_id == str(user_id)
        )
        
        result = await self.db.execute(query)
        workspaces = []
        for row in result:
            workspaces.append({
                "workspace_id": str(row[0]),
                "workspace_name": row[1],
                "role": row[3].value if row[3] else "member",
                "is_default": row[2],
                "joined_at": row[4].isoformat() if row[4] else None
            })
        
        return workspaces
    
    def _validate_password_strength(self, password: str):
        """验证密码强度"""
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters")
        if not any(c.isupper() for c in password):
            raise ValidationError("Password must contain an uppercase letter")
        if not any(c.islower() for c in password):
            raise ValidationError("Password must contain a lowercase letter")
        if not any(c.isdigit() for c in password):
            raise ValidationError("Password must contain at least one digit")
