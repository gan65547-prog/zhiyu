"""
租户Repository实现
"""

from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, func, and_, cast, String, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from infrastructure.database.models import Tenant
from infrastructure.repositories.base import SQLAlchemyRepository
from core.interfaces.repository import TenantRepository
from core.value_objects.pagination import Pagination, Page


class TenantRepositoryImpl(SQLAlchemyRepository[Tenant], TenantRepository):
    """租户Repository实现"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Tenant)

    async def get_by_tenant_id(self, tenant_id: UUID, id: UUID) -> Optional[Tenant]:
        """根据租户ID和实体ID获取实体"""
        result = await self.session.execute(
            select(self.model).where(
                and_(
                    self.model.id == id,
                    self.model.id == tenant_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        filters: dict = None,
        pagination: Pagination = None
    ) -> Page:
        """根据租户ID分页查询实体列表"""
        query = select(self.model).where(self.model.id == tenant_id)

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.where(getattr(self.model, key) == value)

        count_query = select(func.count()).select_from(self.model).where(self.model.id == tenant_id)

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

    async def get_by_email(self, email: str) -> Optional[Tenant]:
        """根据邮箱获取租户"""
        result = await self.session.execute(
            select(self.model).where(self.model.contact_email == email)
        )
        return result.scalar_one_or_none()
    
    async def list(
        self,
        filters: dict = None,
        pagination: Pagination = None
    ) -> Page:
        """查询租户列表，默认过滤掉已删除的租户。

        说明：
        - 历史数据里 plan/status 可能存在与 ORM 枚举标签不一致的值（如 basic/active）。
        - 为避免 ORM 在行反序列化阶段抛 LookupError，这里走文本查询并显式 cast 为文本。
        """
        if filters is None:
            filters = {}

        if "status" not in filters:
            filters["status"] = "active"

        where_clauses = []
        params = {}
        allowed_filters = {"id", "name", "contact_email", "contact_phone", "status", "plan"}
        for key, value in filters.items():
            if key not in allowed_filters or value is None:
                continue
            param_key = f"filter_{key}"
            if key in {"status", "plan"} and isinstance(value, str):
                where_clauses.append(f"LOWER(CAST({key} AS TEXT)) = :{param_key}")
                params[param_key] = value.lower()
            else:
                where_clauses.append(f"{key} = :{param_key}")
                params[param_key] = str(value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        count_sql = text(f"SELECT COUNT(*) FROM tenants {where_sql}")
        total_result = await self.session.execute(count_sql, params)
        total = total_result.scalar_one() or 0

        page = pagination.page if pagination else 1
        page_size = pagination.page_size if pagination else max(total, 1)
        offset = pagination.offset if pagination else 0
        limit = pagination.limit if pagination else max(total, 1)

        list_sql = text(
            f"""
            SELECT
                id,
                name,
                contact_email,
                contact_phone,
                CAST(plan AS TEXT) AS plan,
                CAST(status AS TEXT) AS status,
                metadata AS extra_metadata,
                created_at,
                updated_at
            FROM tenants
            {where_sql}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        )
        list_params = dict(params)
        list_params.update({"limit": limit, "offset": offset})
        result = await self.session.execute(list_sql, list_params)
        items = [dict(row) for row in result.mappings().all()]

        return Page(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )
