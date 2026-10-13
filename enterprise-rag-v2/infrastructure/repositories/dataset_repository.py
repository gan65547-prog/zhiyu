"""
数据集Repository实现
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import Dataset
from infrastructure.repositories.base import SQLAlchemyRepository
from core.value_objects.pagination import Pagination, Page


class DatasetRepositoryImpl(SQLAlchemyRepository[Dataset]):
    """数据集Repository实现"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Dataset)

    async def get_by_workspace(self, workspace_id: UUID) -> List[Dataset]:
        """获取工作空间下的所有数据集"""
        result = await self.session.execute(
            select(self.model).where(self.model.workspace_id == workspace_id)
        )
        return list(result.scalars().all())

    async def list(
        self,
        filters: dict = None,
        pagination: Pagination = None
    ) -> Page:
        """重写list方法以支持工作空间过滤"""
        query = select(self.model)
        count_query = select(func.count()).select_from(self.model)

        filters = dict(filters or {})
        workspace_id = filters.pop("workspace_id", None)
        if workspace_id is not None:
            query = query.where(self.model.workspace_id == workspace_id)
            count_query = count_query.where(self.model.workspace_id == workspace_id)

        for key, value in filters.items():
            if hasattr(self.model, key):
                cond = getattr(self.model, key) == value
                query = query.where(cond)
                count_query = count_query.where(cond)

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
