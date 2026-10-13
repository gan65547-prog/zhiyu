"""
会话权限检查器

负责验证用户对会话的访问权限，支持三种可见性级别：
- PRIVATE: 只有创建者和超级管理员可以访问
- WORKSPACE: 工作空间成员可以访问
- TENANT: 租户内所有用户可以访问

支持元数据审计模式：租户管理员对PRIVATE会话只能查看元数据，不能查看内容
"""

from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from infrastructure.database.models import (
    Conversation,
    ConversationVisibility,
    WorkspaceMember,
    User,
    Workspace,
    Tenant
)
from infrastructure.cache import get_cache
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class PermissionAction(str, Enum):
    """权限操作类型"""
    READ = "read"
    READ_METADATA = "read_metadata"
    UPDATE = "update"
    DELETE = "delete"


class PermissionChecker:
    """
    会话权限检查器
    
    功能：
    1. 验证用户是否有权访问特定会话
    2. 支持基于角色的访问控制（RBAC）
    3. 支持元数据审计模式（租户管理员只能看元数据）
    4. 使用缓存优化性能
    
    权限矩阵：
    | 角色 | PRIVATE | WORKSPACE | TENANT |
    |------|---------|-----------|--------|
    | 创建者 | 完全访问 | 完全访问 | 完全访问 |
    | 工作空间成员 | 无权访问 | 只读访问 | 只读访问 |
    | 工作空间管理员 | 无权访问 | 完全访问 | 完全访问 |
    | 租户管理员 | 元数据只读 | 完全访问 | 完全访问 |
    | 超级管理员 | 完全访问 | 完全访问 | 完全访问 |
    """
    
    CACHE_TTL = 300  # 5分钟缓存过期时间
    
    def __init__(self):
        self._cache = None
        
    async def _get_cache(self):
        """延迟初始化缓存客户端"""
        if self._cache is None:
            self._cache = await get_cache()
        return self._cache
    
    async def check_conversation_access(
        self,
        user_id: str,
        conversation_id: UUID,
        action: PermissionAction,
        session: AsyncSession
    ) -> bool:
        """
        检查用户是否有权限访问会话
        
        Args:
            user_id: 用户ID
            conversation_id: 会话ID
            action: 操作类型（READ/READ_METADATA/UPDATE/DELETE）
            session: 数据库会话
            
        Returns:
            bool: 是否有权限
            
        Note:
            READ_METADATA 用于租户管理员查看PRIVATE会话的元数据
            READ 表示查看完整内容（包括消息）
        """
        
        # 1. 获取会话信息
        conversation = await self._get_conversation(conversation_id, session)
        if not conversation:
            logger.warning(f"Conversation not found: {conversation_id}")
            return False
        
        # 2. 创建者始终有完全权限
        if conversation.user_id == user_id:
            logger.debug(f"User {user_id} is creator of conversation {conversation_id}")
            return True
        
        # 3. 获取用户角色信息（带缓存）
        role_info = await self.get_user_role_info(user_id, session)
        
        # 4. 超级管理员有完全权限
        if role_info.get("is_superuser", False):
            logger.debug(f"User {user_id} is superuser")
            return True
        
        # 5. 租户管理员权限（元数据审计模式）
        if role_info.get("is_tenant_admin", False):
            tenant_id = role_info.get("tenant_id")
            conversation_tenant_id = await self._get_conversation_tenant_id(conversation, session)
            
            if conversation_tenant_id and conversation_tenant_id == tenant_id:
                # 对于PRIVATE会话，只允许查看元数据
                if conversation.visibility == ConversationVisibility.PRIVATE:
                    if action == PermissionAction.READ_METADATA:
                        logger.debug(
                            f"Tenant admin {user_id} can read metadata "
                            f"of private conversation {conversation_id}"
                        )
                        return True
                    else:
                        logger.debug(
                            f"Tenant admin {user_id} cannot {action.value} "
                            f"private conversation {conversation_id}"
                        )
                        return False
                # 对于WORKSPACE和TENANT会话，有完全权限
                else:
                    logger.debug(
                        f"Tenant admin {user_id} has full access to "
                        f"{conversation.visibility} conversation {conversation_id}"
                    )
                    return True
        
        # 6. 根据可见性级别检查权限
        if conversation.visibility == ConversationVisibility.PRIVATE:
            logger.debug(
                f"User {user_id} cannot access private conversation {conversation_id}"
            )
            return False
        
        elif conversation.visibility == ConversationVisibility.WORKSPACE:
            workspace_id = conversation.workspace_id
            if workspace_id in role_info.get("workspace_roles", {}):
                workspace_role = role_info["workspace_roles"][workspace_id]
                
                # 工作空间管理员有完全权限
                if workspace_role in ["owner", "admin"]:
                    if action in [PermissionAction.READ, PermissionAction.UPDATE, 
                                   PermissionAction.DELETE, PermissionAction.READ_METADATA]:
                        logger.debug(
                            f"Workspace admin {user_id} has full access to "
                            f"workspace conversation {conversation_id}"
                        )
                        return True
                
                # 工作空间成员有只读权限
                if action in [PermissionAction.READ, PermissionAction.READ_METADATA]:
                    logger.debug(
                        f"Workspace member {user_id} can read workspace conversation {conversation_id}"
                    )
                    return True
            
            logger.debug(
                f"User {user_id} is not a member of workspace {workspace_id}"
            )
            return False
        
        elif conversation.visibility == ConversationVisibility.TENANT:
            tenant_id = role_info.get("tenant_id")
            conversation_tenant_id = await self._get_conversation_tenant_id(conversation, session)
            
            if conversation_tenant_id and conversation_tenant_id == tenant_id:
                if action in [PermissionAction.READ, PermissionAction.READ_METADATA]:
                    logger.debug(
                        f"Tenant user {user_id} can read tenant conversation {conversation_id}"
                    )
                    return True
            
            logger.debug(
                f"User {user_id} is not in the same tenant as conversation {conversation_id}"
            )
            return False
        
        return False
    
    async def get_user_role_info(
        self,
        user_id: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        获取用户角色信息（带缓存）
        
        Returns:
            {
                "is_superuser": bool,
                "is_tenant_admin": bool,
                "tenant_id": str or None,
                "workspace_roles": {workspace_id: role}
            }
        """
        cache_key = f"user_role:{user_id}"
        
        try:
            # 尝试从缓存获取
            cache = await self._get_cache()
            cached_data = await cache.get(cache_key)
            
            if cached_data:
                logger.debug(f"Cache hit for user {user_id}")
                import json
                return json.loads(cached_data) if isinstance(cached_data, str) else cached_data
        except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as e:
            logger.warning(f"Cache error for user {user_id}: {e}, falling back to database")
        
        # 从数据库获取
        role_info = await self._get_user_role_from_database(user_id, session)
        
        # 写入缓存
        try:
            cache = await self._get_cache()
            import json
            await cache.set(cache_key, json.dumps(role_info), ex=self.CACHE_TTL)
            logger.debug(f"Cached role info for user {user_id}")
        except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as e:
            logger.warning(f"Failed to cache role info for user {user_id}: {e}")
        
        return role_info
    
    async def _get_user_role_from_database(
        self,
        user_id: str,
        session: AsyncSession
    ) -> Dict[str, Any]:
        """从数据库获取用户角色信息"""
        role_info = {
            "is_superuser": False,
            "is_tenant_admin": False,
            "tenant_id": None,
            "workspace_roles": {}
        }
        
        # 查询用户基本信息
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return role_info

        def _normalize_role(raw_role: Any) -> str:
            if raw_role is None:
                return "member"
            if hasattr(raw_role, "value"):
                return str(raw_role.value).lower()
            return str(raw_role).lower()
        
        # 检查是否为超级用户
        role_info["is_superuser"] = getattr(user, 'is_superuser', False)
        
        # 如果是超级用户，直接返回
        if role_info["is_superuser"]:
            return role_info
        
        # 查询工作空间成员关系
        result = await session.execute(
            select(WorkspaceMember).where(WorkspaceMember.user_id == user_id)
        )
        members = result.scalars().all()
        
        for member in members:
            if member.workspace_id:
                role_info["workspace_roles"][str(member.workspace_id)] = _normalize_role(
                    getattr(member, "role", "member")
                )
        
        # 检查是否为租户管理员
        # 通过工作空间关系推断租户ID
        if members:
            first_workspace_id = members[0].workspace_id
            if first_workspace_id:
                result = await session.execute(
                    select(Workspace).where(Workspace.id == first_workspace_id)
                )
                workspace = result.scalar_one_or_none()
                
                if workspace:
                    role_info["tenant_id"] = str(workspace.tenant_id) if hasattr(workspace, 'tenant_id') else None
                    
                    # 检查是否为租户管理员（通过工作空间角色判断）
                    for member in members:
                        if _normalize_role(getattr(member, "role", "")) in ["owner", "admin"]:
                            role_info["is_tenant_admin"] = True
                            break
        
        return role_info
    
    async def _get_conversation(
        self,
        conversation_id: UUID,
        session: AsyncSession
    ) -> Optional[Conversation]:
        """获取会话信息"""
        result = await session.execute(
            select(Conversation).where(Conversation.id == str(conversation_id))
        )
        return result.scalar_one_or_none()
    
    async def _get_conversation_tenant_id(
        self,
        conversation: Conversation,
        session: AsyncSession
    ) -> Optional[str]:
        """获取会话所属的租户ID"""
        if not conversation.workspace_id:
            return None
        
        result = await session.execute(
            select(Workspace).where(Workspace.id == conversation.workspace_id)
        )
        workspace = result.scalar_one_or_none()
        
        if workspace and hasattr(workspace, 'tenant_id'):
            return str(workspace.tenant_id)
        
        return None
    
    @staticmethod
    async def invalidate_user_cache(user_id: str) -> None:
        """使用户角色缓存失效"""
        try:
            from infrastructure.cache import get_cache as _get_cache
            cache = await _get_cache()
            cache_key = f"user_role:{user_id}"
            await cache.delete(cache_key)
            logger.info(f"Invalidated cache for user {user_id}")
        except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as e:
            logger.error(f"Failed to invalidate cache for user {user_id}: {e}")
    
    @staticmethod
    async def invalidate_workspace_cache(workspace_id: str) -> None:
        """使工作空间所有成员缓存失效"""
        try:
            from infrastructure.cache import get_cache as _get_cache
            from sqlalchemy.ext.asyncio import create_async_engine
            from sqlalchemy.orm import sessionmaker
            from core.config import get_settings
            
            settings = get_settings()
            engine = create_async_engine(settings.database.url)
            async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            
            async with async_session() as session:
                result = await session.execute(
                    select(WorkspaceMember.user_id).where(
                        WorkspaceMember.workspace_id == workspace_id
                    )
                )
                member_ids = result.scalars().all()
                
                cache = await _get_cache()
                
                for member_id in member_ids:
                    cache_key = f"user_role:{member_id}"
                    await cache.delete(cache_key)
                
                logger.info(
                    f"Invalidated cache for {len(member_ids)} members of workspace {workspace_id}"
                )
        except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as e:
            logger.error(f"Failed to invalidate workspace cache for {workspace_id}: {e}")
