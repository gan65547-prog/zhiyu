"""
基础Repository类
"""

from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.sql import func
from datetime import datetime, timezone

from core.interfaces.repository import IRepository
from core.value_objects.pagination import PaginationParams, PaginatedResult

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType], IRepository):
    """基础Repository实现"""

    def __init__(self, model: Type[ModelType], db_session: AsyncSession):
        self.model = model
        self.db_session = db_session

    async def create(self, obj_in: CreateSchemaType) -> ModelType:
        """创建记录"""
        obj_dict = obj_in.model_dump() if hasattr(obj_in, "model_dump") else dict(obj_in)
        
        # 添加时间戳
        now = datetime.now(timezone.utc)
        obj_dict["created_at"] = now
        obj_dict["updated_at"] = now
        
        db_obj = self.model(**obj_dict)
        self.db_session.add(db_obj)
        await self.db_session.flush()
        await self.db_session.refresh(db_obj)
        return db_obj

    async def get(self, id: Any) -> Optional[ModelType]:
        """根据ID获取记录"""
        stmt = select(self.model).where(self.model.id == id)
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None
    ) -> List[ModelType]:
        """获取多条记录"""
        stmt = select(self.model)
        
        # 应用过滤条件
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    if value is None:
                        stmt = stmt.where(getattr(self.model, key).is_(None))
                    else:
                        stmt = stmt.where(getattr(self.model, key) == value)
        
        # 应用排序
        if order_by:
            if order_by.startswith("-"):
                stmt = stmt.order_by(getattr(self.model, order_by[1:]).desc())
            else:
                stmt = stmt.order_by(getattr(self.model, order_by))
        
        # 应用分页
        stmt = stmt.offset(skip).limit(limit)
        
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def get_paginated(
        self,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> PaginatedResult[ModelType]:
        """获取分页结果"""
        # 查询数据
        items = await self.get_multi(
            skip=pagination.skip,
            limit=pagination.limit,
            filters=filters,
            order_by=pagination.order_by
        )
        
        # 查询总数
        count_stmt = select(func.count()).select_from(self.model)
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    if value is None:
                        count_stmt = count_stmt.where(getattr(self.model, key).is_(None))
                    else:
                        count_stmt = count_stmt.where(getattr(self.model, key) == value)
        
        total_result = await self.db_session.execute(count_stmt)
        total = total_result.scalar()
        
        return PaginatedResult(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.limit,
            total_pages=(total + pagination.limit - 1) // pagination.limit if pagination.limit > 0 else 0
        )

    async def update(self, id: Any, obj_in: UpdateSchemaType) -> Optional[ModelType]:
        """更新记录"""
        obj_dict = obj_in.model_dump(exclude_unset=True) if hasattr(obj_in, "model_dump") else dict(obj_in)
        
        # 更新更新时间
        obj_dict["updated_at"] = datetime.now(timezone.utc)
        
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**obj_dict)
            .returning(self.model)
        )
        
        result = await self.db_session.execute(stmt)
        await self.db_session.flush()
        
        if result.rowcount > 0:
            # 重新查询获取完整对象
            return await self.get(id)
        return None

    async def delete(self, id: Any) -> bool:
        """删除记录"""
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.db_session.execute(stmt)
        await self.db_session.flush()
        return result.rowcount > 0

    async def exists(self, id: Any) -> bool:
        """检查记录是否存在"""
        stmt = select(func.count()).select_from(self.model).where(self.model.id == id)
        result = await self.db_session.execute(stmt)
        count = result.scalar()
        return count > 0

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """统计记录数量"""
        stmt = select(func.count()).select_from(self.model)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    if value is None:
                        stmt = stmt.where(getattr(self.model, key).is_(None))
                    else:
                        stmt = stmt.where(getattr(self.model, key) == value)
        
        result = await self.db_session.execute(stmt)
        return result.scalar()