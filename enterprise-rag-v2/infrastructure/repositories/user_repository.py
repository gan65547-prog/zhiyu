"""
用户Repository实现
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import User
from infrastructure.repositories.base import SQLAlchemyRepository
from core.interfaces.repository import Repository
from core.value_objects.pagination import Pagination, Page


class UserRepositoryImpl(SQLAlchemyRepository[User]):
    """用户Repository实现"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户（大小写不敏感）"""
        from sqlalchemy import func
        result = await self.session.execute(
            select(self.model).where(func.lower(self.model.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        result = await self.session.execute(
            select(self.model).where(self.model.username == username)
        )
        return result.scalar_one_or_none()

    async def get_by_tenant(self, tenant_id: UUID) -> List[User]:
        """获取租户下的所有用户"""
        result = await self.session.execute(
            select(self.model).where(self.model.tenant_id == tenant_id)
        )
        return list(result.scalars().all())

    async def list(
        self,
        filters: dict = None,
        pagination: Pagination = None
    ) -> Page:
        """重写list方法以支持租户过滤"""
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
