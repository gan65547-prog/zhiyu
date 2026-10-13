"""
会话Repository实现
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infrastructure.database.models import Conversation, Message
from infrastructure.repositories.base import SQLAlchemyRepository
from core.value_objects.pagination import Pagination, Page


class ConversationRepositoryImpl(SQLAlchemyRepository[Conversation]):
    """会话Repository实现"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Conversation)

    async def get_by_dataset(self, dataset_id: UUID) -> List[Conversation]:
        """获取数据集下的所有会话"""
        result = await self.session.execute(
            select(self.model)
            .where(self.model.dataset_id == dataset_id)
            .order_by(self.model.updated_at.desc())
        )
        return list(result.scalars().all())

    async def list(
        self,
        filters: dict = None,
        pagination: Pagination = None
    ) -> Page:
        """重写list方法以支持数据集过滤"""
        query = select(self.model)

        if filters and filters.get("dataset_id"):
            query = query.where(self.model.dataset_id == filters["dataset_id"])
            del filters["dataset_id"]

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


class MessageRepositoryImpl(SQLAlchemyRepository[Message]):
    """消息Repository实现"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Message)

    async def get_by_conversation(self, conversation_id: UUID) -> List[Message]:
        """获取会话下的所有消息"""
        result = await self.session.execute(
            select(self.model)
            .where(self.model.conversation_id == conversation_id)
            .order_by(self.model.created_at)
        )
        return list(result.scalars().all())

    async def count_by_conversation(self, conversation_id: UUID) -> int:
        """获取会话的消息数量"""
        result = await self.session.execute(
            select(func.count()).select_from(self.model).where(self.model.conversation_id == conversation_id)
        )
        return result.scalar_one()
