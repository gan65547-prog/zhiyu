"""
工作空间Repository实现
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infrastructure.database.models import Workspace, WorkspaceMember
from infrastructure.repositories.base import SQLAlchemyRepository
from core.interfaces.repository import WorkspaceRepository
from core.value_objects.pagination import Pagination, Page
from infrastructure.logging.logger import get_logger


class WorkspaceRepositoryImpl(SQLAlchemyRepository[Workspace], WorkspaceRepository):
    """工作空间Repository实现"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Workspace)
        self.logger = get_logger(__name__)

    async def get_by_workspace_id(self, workspace_id: UUID, id: UUID) -> Optional[Workspace]:
        """根据工作空间ID和实体ID获取实体"""
        result = await self.session.execute(
            select(self.model).where(
                and_(
                    self.model.id == id,
                    self.model.id == workspace_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        filters: dict = None,
        pagination: Pagination = None
    ) -> Page:
        """根据工作空间ID分页查询实体列表"""
        query = select(self.model).where(self.model.id == workspace_id)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        count_query = select(func.count()).select_from(self.model).where(self.model.id == workspace_id)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        if pagination:
            query = query.offset(pagination.offset).limit(pagination.limit)

        result = await self.session.execute(query)
        items = result.scalars().all()

        return Page(
            items=list(items),
            total=total,
            page=pagination.page if pagination else 1,
            page_size=pagination.page_size if pagination else total
        )

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        keyword: str = None,
        pagination: Pagination = None
    ) -> Page:
        """根据租户ID列出工作空间"""
        tenant_id_str = str(tenant_id)
        query = select(self.model).where(self.model.tenant_id == tenant_id_str)

        if keyword:
            query = query.where(self.model.name.ilike(f"%{keyword}%"))

        count_query = select(func.count()).select_from(self.model).where(self.model.tenant_id == tenant_id_str)
        if keyword:
            count_query = count_query.where(self.model.name.ilike(f"%{keyword}%"))

        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        if pagination:
            query = query.offset(pagination.offset).limit(pagination.limit)

        result = await self.session.execute(query)
        items = result.scalars().all()

        return Page(
            items=list(items),
            total=total,
            page=pagination.page if pagination else 1,
            page_size=pagination.page_size if pagination else total
        )

    async def list_by_user_and_tenant(
        self,
        user_id: UUID,
        tenant_id: UUID,
        keyword: str = None,
        pagination: Pagination = None
    ) -> Page:
        """根据用户ID和租户ID列出用户是成员的工作空间"""
        tenant_id_str = str(tenant_id)
        user_id_str = str(user_id)
        
        query = (
            select(self.model)
            .join(WorkspaceMember, self.model.id == WorkspaceMember.workspace_id)
            .where(
                and_(
                    self.model.tenant_id == tenant_id_str,
                    WorkspaceMember.user_id == user_id_str
                )
            )
        )

        if keyword:
            query = query.where(self.model.name.ilike(f"%{keyword}%"))

        count_query = (
            select(func.count())
            .select_from(self.model)
            .join(WorkspaceMember, self.model.id == WorkspaceMember.workspace_id)
            .where(
                and_(
                    self.model.tenant_id == tenant_id_str,
                    WorkspaceMember.user_id == user_id_str
                )
            )
        )
        if keyword:
            count_query = count_query.where(self.model.name.ilike(f"%{keyword}%"))

        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        if pagination:
            query = query.offset(pagination.offset).limit(pagination.limit)

        result = await self.session.execute(query)
        items = result.scalars().all()

        return Page(
            items=list(items),
            total=total,
            page=pagination.page if pagination else 1,
            page_size=pagination.page_size if pagination else total
        )


class WorkspaceMemberRepositoryImpl(SQLAlchemyRepository[WorkspaceMember]):
    """工作空间成员Repository实现"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, WorkspaceMember)
        self.logger = get_logger(__name__)

    async def get_by_workspace_and_user(self, workspace_id: UUID, user_id: UUID) -> Optional[WorkspaceMember]:
        """根据工作空间ID和用户ID获取成员"""
        self.logger.debug(f"Checking workspace member: workspace_id={workspace_id}, user_id={user_id}")
        result = await self.session.execute(
            select(self.model).where(
                and_(
                    self.model.workspace_id == str(workspace_id),
                    self.model.user_id == str(user_id)
                )
            )
        )
        member = result.scalar_one_or_none()
        self.logger.debug(f"Found member: {member is not None}")
        return member

    async def list_by_workspace(self, workspace_id: UUID) -> List[WorkspaceMember]:
        """列出工作空间的所有成员"""
        result = await self.session.execute(
            select(self.model)
            .options(selectinload(self.model.user))
            .where(self.model.workspace_id == str(workspace_id))
        )
        return list(result.scalars().all())

    async def list_by_user(self, user_id: UUID) -> List[WorkspaceMember]:
        """列出用户加入的所有工作空间"""
        result = await self.session.execute(
            select(self.model)
            .options(selectinload(self.model.workspace))
            .where(self.model.user_id == str(user_id))
        )
        return list(result.scalars().all())
