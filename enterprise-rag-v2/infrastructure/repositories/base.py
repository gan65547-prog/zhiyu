"""
Repository模式实现

提供通用数据访问层的SQLAlchemy实现
"""

from typing import Generic, TypeVar, Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.interfaces.repository import Repository
from core.entities.base import BaseEntity
from core.value_objects.pagination import Pagination, Page


T = TypeVar('T', bound=BaseEntity)


class SQLAlchemyRepository(Generic[T]):
    """SQLAlchemy Repository基类"""

    def __init__(self, session: AsyncSession, model: type):
        self.session = session
        self.model = model

    async def create(self, entity: T) -> T:
        """创建实体"""
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def get_by_id(self, id: UUID) -> Optional[T]:
        """根据ID获取实体"""
        id_str = str(id)
        result = await self.session.execute(
            select(self.model).where(self.model.id == id_str)
        )
        return result.scalar_one_or_none()

    async def update(self, entity: T) -> T:
        """更新实体"""
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, id: UUID) -> bool:
        """删除实体"""
        id_str = str(id)
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id_str)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def exists(self, id: UUID) -> bool:
        """检查实体是否存在"""
        id_str = str(id)
        result = await self.session.execute(
            select(func.count()).select_from(self.model).where(self.model.id == id_str)
        )
        return result.scalar_one() > 0

    async def list(
        self,
        filters: Dict[str, Any] = None,
        pagination: Pagination = None
    ) -> Page:
        """分页查询实体列表"""
        query = select(self.model)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        count_query = select(func.count()).select_from(self.model)
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    count_query = count_query.where(getattr(self.model, key) == value)

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

    async def batch_create(self, entities: List[T]) -> List[T]:
        """批量创建实体"""
        self.session.add_all(entities)
        await self.session.flush()
        for entity in entities:
            await self.session.refresh(entity)
        return entities

    async def batch_update(self, entities: List[T]) -> List[T]:
        """批量更新实体"""
        for entity in entities:
            await self.session.merge(entity)
        await self.session.flush()
        return entities

    async def batch_delete(self, ids: List[UUID]) -> int:
        """批量删除实体"""
        id_strs = [str(id) for id in ids]
        result = await self.session.execute(
            delete(self.model).where(self.model.id.in_(id_strs))
        )
        await self.session.flush()
        return result.rowcount

    async def batch_get(self, ids: List[UUID]) -> List[T]:
        """批量获取实体"""
        id_strs = [str(id) for id in ids]
        result = await self.session.execute(
            select(self.model).where(self.model.id.in_(id_strs))
        )
        return list(result.scalars().all())
