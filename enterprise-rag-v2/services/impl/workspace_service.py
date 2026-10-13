"""
工作空间服务实现
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path
import inspect
from infrastructure.logging.logger import get_logger

from infrastructure.database.models import (
    Workspace,
    WorkspaceMember,
    User,
    WorkspaceRole,
    Dataset,
    Document,
    _coerce_workspace_role,
)
from infrastructure.repositories.workspace_repository import (
    WorkspaceRepositoryImpl,
    WorkspaceMemberRepositoryImpl
)
from core.decorators import log_exceptions
from services.interfaces.workspace_service import WorkspaceService
from core.value_objects.pagination import Pagination, Page
from core.rag.collection_manager import CollectionManager
from core.rag.vector_store import create_vector_store

logger = get_logger(__name__)


async def get_public_workspaces_for_tenant(
    session: AsyncSession, tenant_id: str
) -> list:
    """Return all public workspaces for a tenant (extra_metadata.is_public_workspace=True)."""
    from sqlalchemy import select as _select
    from infrastructure.database.models import Workspace as _Workspace

    result = await session.execute(
        _select(_Workspace).where(_Workspace.tenant_id == tenant_id)
    )
    return [
        ws for ws in result.scalars().all()
        if ws.extra_metadata and ws.extra_metadata.get("is_public_workspace") is True
    ]


class WorkspaceServiceImpl(WorkspaceService):
    """工作空间服务实现"""

    def __init__(self, session: AsyncSession, quota_service=None):
        self._session = session
        self._quota_service = quota_service
        self.workspace_repo = WorkspaceRepositoryImpl(session)
        self.member_repo = WorkspaceMemberRepositoryImpl(session)

    @property
    def session(self) -> AsyncSession:
        """获取数据库会话"""
        return self._session

    async def _is_tenant_admin(self, user_id: UUID) -> bool:
        """判断用户是否为租户管理员（任一工作空间 owner/admin）。"""
        result = await self.session.execute(
            select(WorkspaceMember.role).where(WorkspaceMember.user_id == str(user_id))
        )
        for (role_val,) in result.all():
            if _coerce_workspace_role(role_val) in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
                return True
        return False

    async def _sync_tenant_admin_workspace_memberships(
        self, tenant_id: UUID, user_id: UUID
    ) -> None:
        """为租户管理员补齐同租户下缺失的工作空间成员关系（自愈历史数据）。"""
        if not await self._is_tenant_admin(user_id):
            return

        tenant_id_str = str(tenant_id)
        user_id_str = str(user_id)

        all_ws_result = await self.session.execute(
            select(Workspace.id).where(Workspace.tenant_id == tenant_id_str)
        )
        all_workspace_ids = {str(row[0]) for row in all_ws_result.all()}
        if not all_workspace_ids:
            return

        member_ws_result = await self.session.execute(
            select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id_str)
        )
        member_workspace_ids = {str(row[0]) for row in member_ws_result.all()}

        missing_workspace_ids = all_workspace_ids - member_workspace_ids
        if not missing_workspace_ids:
            return

        for ws_id in missing_workspace_ids:
            self.session.add(
                WorkspaceMember(
                    workspace_id=ws_id,
                    user_id=user_id_str,
                    role=WorkspaceRole.ADMIN,
                )
            )
        await self.session.flush()
        logger.info(
            "Synced tenant-admin workspace memberships: tenant=%s user=%s added=%s",
            tenant_id_str,
            user_id_str,
            len(missing_workspace_ids),
        )

    async def _cleanup_workspace_files(self, workspace_id_str: str) -> None:
        """清理工作空间下文档文件（最佳努力，不因单文件失败中断）"""
        result = await self.session.execute(
            select(Document.file_path)
            .join(Dataset, Dataset.id == Document.dataset_id)
            .where(Dataset.workspace_id == workspace_id_str)
        )
        file_paths = [row[0] for row in result.all() if row and row[0]]

        for file_path in file_paths:
            try:
                path = Path(file_path)
                if path.exists() and path.is_file():
                    path.unlink()
            except OSError as e:
                logger.warning("Failed to delete workspace file %s: %s", file_path, e)

    async def _cleanup_workspace_vector_collection(self, workspace_id_str: str) -> None:
        """清理工作空间向量集合（最佳努力）"""
        collection_name = CollectionManager.get_workspace_collection_name(workspace_id_str)
        vector_store = await create_vector_store(collection_name=collection_name, use_memory_fallback=True)

        try:
            # EmbeddedQdrantStore / QdrantVectorStore 都实现了 _get_client + collection_name
            if hasattr(vector_store, "_get_client"):
                client = vector_store._get_client()
                if inspect.isawaitable(client):
                    client = await client

                # 嵌入式Qdrant客户端（qdrant-client）
                if hasattr(client, "collection_exists"):
                    if client.collection_exists(collection_name):
                        client.delete_collection(collection_name=collection_name)
                # HTTP客户端（httpx.AsyncClient）
                elif hasattr(client, "delete") and hasattr(vector_store, "config"):
                    response = await client.delete(
                        f"{vector_store.config.qdrant_url}/collections/{collection_name}"
                    )
                    if response.status_code not in (200, 202, 404):
                        logger.warning(
                            "Unexpected response when deleting collection %s: %s",
                            collection_name,
                            response.status_code,
                        )
            elif hasattr(vector_store, "_instances"):
                # MemoryVectorStore: 清理对应内存集合实例
                vector_store.__class__._instances.pop(collection_name, None)
        except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as e:
            logger.warning("Failed to cleanup vector collection %s: %s", collection_name, e)

    async def create_workspace(
        self,
        tenant_id: UUID,
        name: str,
        creator_id: UUID,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        is_default: bool = False
    ) -> dict:
        """创建工作空间"""
        if self._quota_service:
            await self._quota_service.check_quota(str(tenant_id), "workspaces")

        workspace = Workspace(
            tenant_id=str(tenant_id),
            name=name,
            description=description,
            is_default=is_default,
            extra_metadata=metadata or {}
        )

        created = await self.workspace_repo.create(workspace)

        # 自动添加创建者为成员（OWNER角色）
        member = WorkspaceMember(
            workspace_id=created.id,
            user_id=str(creator_id),
            role=WorkspaceRole.OWNER
        )
        await self.member_repo.create(member)

        # 为同租户其他租户管理员自动补齐新工作空间访问（ADMIN角色）
        tenant_admin_result = await self.session.execute(
            select(WorkspaceMember.user_id, WorkspaceMember.role)
            .join(Workspace, WorkspaceMember.workspace_id == Workspace.id)
            .where(Workspace.tenant_id == str(tenant_id))
        )
        tenant_admin_user_ids = set()
        for row in tenant_admin_result.all():
            candidate_user_id = str(row[0])
            candidate_role = _coerce_workspace_role(row[1])
            if candidate_role in (WorkspaceRole.OWNER, WorkspaceRole.ADMIN):
                tenant_admin_user_ids.add(candidate_user_id)

        creator_id_str = str(creator_id)
        for admin_user_id in tenant_admin_user_ids:
            if admin_user_id == creator_id_str:
                continue
            exists_result = await self.session.execute(
                select(WorkspaceMember.id).where(
                    WorkspaceMember.workspace_id == created.id,
                    WorkspaceMember.user_id == admin_user_id,
                )
            )
            if exists_result.scalar_one_or_none():
                continue
            self.session.add(
                WorkspaceMember(
                    workspace_id=created.id,
                    user_id=admin_user_id,
                    role=WorkspaceRole.ADMIN,
                )
            )

        await self.session.flush()

        # 更新用户当前工作空间
        user = await self.session.get(User, str(creator_id))
        if user:
            user.current_workspace_id = created.id
            await self.session.flush()

        return {
            "id": str(created.id),
            "tenant_id": str(created.tenant_id),
            "name": created.name,
            "description": created.description,
            "is_default": created.is_default,
            "member_count": 1,
            "dataset_count": 0,
            "metadata": created.extra_metadata,
            "created_at": created.created_at.isoformat() if created.created_at else None,
            "updated_at": created.updated_at.isoformat() if created.updated_at else None
        }

    async def get_workspace(self, workspace_id: UUID) -> Optional[dict]:
        """获取工作空间详情"""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            return None

        return {
            "id": str(workspace.id),
            "tenant_id": str(workspace.tenant_id),
            "name": workspace.name,
            "description": workspace.description,
            "is_default": workspace.is_default,
            "metadata": workspace.extra_metadata,
            "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
            "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None
        }

    async def update_workspace(
        self,
        workspace_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        """更新工作空间"""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise ValueError("工作空间不存在")

        if name is not None:
            workspace.name = name
        if description is not None:
            workspace.description = description
        if metadata is not None:
            workspace.extra_metadata = metadata

        updated = await self.workspace_repo.update(workspace)

        return {
            "id": str(updated.id),
            "tenant_id": str(updated.tenant_id),
            "name": updated.name,
            "description": updated.description,
            "is_default": updated.is_default,
            "metadata": updated.extra_metadata,
            "created_at": updated.created_at.isoformat() if updated.created_at else None,
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None
        }

    async def delete_workspace(self, workspace_id: UUID) -> bool:
        """删除工作空间"""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            return False

        workspace_id_str = str(workspace_id)
        tenant_id_str = str(workspace.tenant_id)

        # 清理工作空间关联的外部资源（文件/向量集合）
        await self._cleanup_workspace_files(workspace_id_str)
        await self._cleanup_workspace_vector_collection(workspace_id_str)

        # 先为受影响用户切换 current_workspace，避免外键 CASCADE 误删用户
        fallback_workspace_result = await self.session.execute(
            select(Workspace)
            .where(
                Workspace.tenant_id == tenant_id_str,
                Workspace.id != workspace_id_str
            )
            .order_by(Workspace.created_at.asc())
            .limit(1)
        )
        fallback_workspace = fallback_workspace_result.scalar_one_or_none()

        affected_users_result = await self.session.execute(
            select(User).where(User.current_workspace_id == workspace_id_str)
        )
        affected_users = affected_users_result.scalars().all()
        for user in affected_users:
            user.current_workspace_id = str(fallback_workspace.id) if fallback_workspace else None

        if affected_users:
            logger.warning(
                "Workspace %s deleted, reassigned %d users to %s",
                workspace_id_str,
                len(affected_users),
                str(fallback_workspace.id) if fallback_workspace else None,
            )
            await self.session.flush()

        await self.workspace_repo.delete(workspace_id)
        return True

    async def is_workspace_member(
        self,
        workspace_id: UUID,
        user_id: UUID
    ) -> bool:
        """检查用户是否是工作空间成员"""
        member = await self.member_repo.get_by_workspace_and_user(workspace_id, user_id)
        return member is not None

    @log_exceptions(__name__)
    async def list_workspaces(
        self,
        tenant_id: UUID,
        user_id: UUID,
        keyword: Optional[str] = None,
        pagination: Optional[Pagination] = None
    ) -> Page:
        """查询工作空间列表（仅用户是成员的）"""
        tenant_id_str = str(tenant_id)
        user_id_str = str(user_id)
        logger.debug(f"Listing workspaces for user: {user_id_str}, tenant: {tenant_id_str}, keyword: {keyword}")

        # 自愈：租户管理员应自动拥有本租户全部工作空间访问
        await self._sync_tenant_admin_workspace_memberships(tenant_id=tenant_id, user_id=user_id)

        result = await self.workspace_repo.list_by_user_and_tenant(user_id, tenant_id, keyword, pagination)
        logger.debug(f"Found {result.total} workspaces for user: {user_id_str}")

        items = []
        for ws in result.items:
            items.append({
                "id": str(ws.id),
                "tenant_id": str(ws.tenant_id),
                "name": ws.name,
                "description": ws.description,
                "is_default": ws.is_default,
                "metadata": ws.extra_metadata,
                "created_at": ws.created_at.isoformat() if ws.created_at else None,
                "updated_at": ws.updated_at.isoformat() if ws.updated_at else None
            })

        page = Page(
            items=items,
            total=result.total,
            page=result.page,
            page_size=result.page_size
        )
        logger.debug(f"Returning {len(items)} workspaces for user: {user_id_str}")
        return page

    async def add_member(
        self,
        workspace_id: UUID,
        user_id: UUID,
        role: str = "member"
    ) -> dict:
        """添加工作空间成员"""
        existing = await self.member_repo.get_by_workspace_and_user(workspace_id, user_id)
        if existing:
            raise ValueError("用户已是工作空间成员")

        member = WorkspaceMember(
            workspace_id=str(workspace_id),
            user_id=str(user_id),
            role=role
        )

        created = await self.member_repo.create(member)

        return {
            "id": str(created.id),
            "workspace_id": str(created.workspace_id),
            "user_id": str(created.user_id),
            "role": created.role.value if hasattr(created.role, 'value') else created.role,
            "joined_at": created.joined_at.isoformat() if created.joined_at else None
        }

    async def remove_member(self, workspace_id: UUID, user_id: UUID) -> bool:
        """移除工作空间成员"""
        member = await self.member_repo.get_by_workspace_and_user(workspace_id, user_id)
        if not member:
            return False

        await self.member_repo.delete(member.id)
        return True

    async def update_member_role(
        self,
        workspace_id: UUID,
        user_id: UUID,
        role: str
    ) -> dict:
        """更新成员角色"""
        member = await self.member_repo.get_by_workspace_and_user(workspace_id, user_id)
        if not member:
            raise ValueError("成员不存在")

        member.role = role
        updated = await self.member_repo.update(member)

        return {
            "id": str(updated.id),
            "workspace_id": str(updated.workspace_id),
            "user_id": str(updated.user_id),
            "role": updated.role.value if hasattr(updated.role, 'value') else updated.role,
            "joined_at": updated.joined_at.isoformat() if updated.joined_at else None
        }

    async def list_members(self, workspace_id: UUID) -> List[dict]:
        """获取工作空间成员列表"""
        members = await self.member_repo.list_by_workspace(workspace_id)

        result = []
        for member in members:
            # 保持与前端 WorkspaceMember 类型匹配的数据结构
            result.append({
                "id": str(member.id),
                "workspace_id": str(member.workspace_id),
                "user_id": str(member.user_id),
                "role": member.role.value if hasattr(member.role, 'value') else member.role,
                "user": {
                    "id": str(member.user.id),
                    "username": member.user.username,
                    "email": member.user.email
                } if member.user else None,
                "joined_at": member.joined_at.isoformat() if member.joined_at else None
            })

        return result

    async def switch_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID
    ) -> dict:
        """切换用户当前工作空间（验证用户是否是成员）"""
        logger.debug(
            "Switching workspace: workspace_id=%s user_id=%s",
            workspace_id,
            user_id,
        )
        
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise ValueError("工作空间不存在")
        
        # 验证用户是否是工作空间成员
        is_member = await self.is_workspace_member(workspace_id, user_id)
        if not is_member:
            raise ValueError("不是工作空间成员，无法切换")

        user_id_str = str(user_id)
        result = await self.session.execute(
            select(User).where(User.id == user_id_str)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("用户不存在")

        user.current_workspace_id = str(workspace_id)
        await self.session.flush()
        await self.session.refresh(user)
        logger.debug("Workspace switched successfully: user_id=%s workspace_id=%s", user_id_str, workspace_id)

        return {
            "id": str(workspace.id),
            "tenant_id": str(workspace.tenant_id),
            "name": workspace.name,
            "description": workspace.description,
            "is_default": workspace.is_default,
            "metadata": workspace.extra_metadata,
            "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
            "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None
        }
    

    
    async def get_workspace_with_member_check(
        self,
        workspace_id: UUID,
        user_id: UUID
    ) -> Optional[dict]:
        """获取工作空间详情（验证用户是否是成员）"""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            return None
        
        # 验证用户是否是工作空间成员
        is_member = await self.is_workspace_member(workspace_id, user_id)
        if not is_member:
            return None

        return {
            "id": str(workspace.id),
            "tenant_id": str(workspace.tenant_id),
            "name": workspace.name,
            "description": workspace.description,
            "is_default": workspace.is_default,
            "metadata": workspace.extra_metadata,
            "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
            "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None
        }

    @log_exceptions(__name__)
    async def verify_system_template_access(self, workspace_id: UUID, user_id: UUID) -> None:
        """验证用户是否有权访问系统模板工作空间"""
        workspace = await self.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise ValueError("工作空间不存在")
        
        # 系统模板工作空间只允许超级管理员访问
        if workspace.extra_metadata.get("is_system_template"):
            user_id_str = str(user_id)
            result = await self.session.execute(
                select(User).where(User.id == user_id_str)
            )
            user = result.scalar_one_or_none()
            if not user or not user.is_superuser:
                raise PermissionError("系统模板工作空间仅超级管理员可访问")

    async def get_current_workspace(
        self,
        user_id: UUID,
        tenant_id: Optional[str] = None,
    ) -> Optional[dict]:
        """获取用户当前工作空间"""
        user_id_str = str(user_id)
        logger.debug(f"Getting current workspace for user: {user_id_str}")
        
        result = await self.session.execute(
            select(User).where(User.id == user_id_str)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"User not found: {user_id_str}")
            return None

        if not user.current_workspace_id:
            logger.debug(f"User {user_id_str} has no current workspace, finding first workspace")
            # 直接使用user.tenant_id，因为它已经是字符串类型
            tenant_id_str = user.tenant_id
            first_result = await self.session.execute(
                select(Workspace)
                .where(Workspace.tenant_id == tenant_id_str)
                .order_by(Workspace.created_at)
                .limit(1)
            )
            workspace = first_result.scalar_one_or_none()
            
            if workspace:
                logger.debug(f"Found first workspace: {workspace.id} for user: {user_id_str}")
                user.current_workspace_id = str(workspace.id)
                await self.session.flush()
                logger.debug(f"Updated user {user_id_str} current workspace to: {workspace.id}")
            else:
                logger.warning(f"No workspaces found for tenant: {tenant_id_str}")
                return None
        else:
            logger.debug(f"User {user_id_str} has current workspace: {user.current_workspace_id}")
            workspace_result = await self.session.execute(
                select(Workspace).where(Workspace.id == user.current_workspace_id)
            )
            workspace = workspace_result.scalar_one_or_none()

        if not workspace:
            logger.warning(f"Workspace not found: {user.current_workspace_id}")
            return None

        if tenant_id is not None and str(workspace.tenant_id) != str(tenant_id):
            logger.warning(
                "Workspace %s tenant_id=%s does not match JWT tenant_id=%s for user %s",
                workspace.id,
                workspace.tenant_id,
                tenant_id,
                user_id_str,
            )
            return None

        logger.debug(f"Returning workspace: {workspace.id} for user: {user_id_str}")
        return {
            "id": str(workspace.id),
            "tenant_id": str(workspace.tenant_id),
            "name": workspace.name,
            "description": workspace.description,
            "is_default": workspace.is_default,
            "metadata": workspace.extra_metadata,
            "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
            "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None
        }