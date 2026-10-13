"""
文档Repository实现
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import Document, DocumentChunk
from infrastructure.repositories.base import SQLAlchemyRepository
from core.value_objects.pagination import Pagination, Page


class DocumentRepositoryImpl(SQLAlchemyRepository[Document]):
    """文档Repository实现"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Document)

    async def get_by_dataset(self, dataset_id: UUID) -> List[Document]:
        """获取数据集下的所有文档"""
        # 将UUID转换为字符串格式（数据库中存储的是字符串）
        dataset_id_str = str(dataset_id) if hasattr(dataset_id, 'hex') else dataset_id
        result = await self.session.execute(
            select(self.model).where(self.model.dataset_id == dataset_id_str)
        )
        return list(result.scalars().all())

    async def get_by_dataset_and_name(self, dataset_id: str, file_name: str) -> Optional[Document]:
        """根据数据集ID和文件名获取文档"""
        result = await self.session.execute(
            select(self.model).where(
                and_(
                    self.model.dataset_id == dataset_id,
                    self.model.file_name == file_name
                )
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        filters: dict = None,
        pagination: Pagination = None
    ) -> Page:
        """重写list方法以支持数据集过滤"""
        query = select(self.model)
        count_query = select(func.count()).select_from(self.model)

        dataset_id_str = None
        if filters and filters.get("dataset_id"):
            # 将UUID转换为字符串格式（数据库中存储的是字符串）
            dataset_id = filters["dataset_id"]
            dataset_id_str = str(dataset_id) if hasattr(dataset_id, 'hex') else dataset_id
            query = query.where(self.model.dataset_id == dataset_id_str)
            del filters["dataset_id"]

        if dataset_id_str:
            # 统计总数时也必须应用同样的数据集过滤，否则会出现分页页码虚高、点击后空列表
            count_query = count_query.where(self.model.dataset_id == dataset_id_str)

        keyword = None
        if filters:
            keyword = filters.pop("keyword", None)
        if keyword:
            pattern = f"%{keyword}%"
            keyword_filter = or_(
                self.model.file_name.ilike(pattern),
                self.model.file_path.ilike(pattern),
            )
            query = query.where(keyword_filter)
            count_query = count_query.where(keyword_filter)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)
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


class DocumentChunkRepositoryImpl(SQLAlchemyRepository[DocumentChunk]):
    """文档块Repository实现"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, DocumentChunk)

    async def get_by_document(self, document_id: UUID) -> List[DocumentChunk]:
        """获取文档下的所有块"""
        result = await self.session.execute(
            select(self.model)
            .where(self.model.document_id == document_id)
            .order_by(self.model.chunk_index)
        )
        return list(result.scalars().all())

    async def count_by_document(self, document_id: UUID) -> int:
        """获取文档的块数量"""
        result = await self.session.execute(
            select(func.count()).select_from(self.model).where(self.model.document_id == document_id)
        )
        return result.scalar_one()
