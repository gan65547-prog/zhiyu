"""
用户Repository实现
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from infrastructure.database.models import User
from core.schemas.user import UserCreate, UserUpdate
from .base_repository import BaseRepository


class UserRepository(BaseRepository[User, UserCreate, UserUpdate]):
    """用户Repository"""

    def __init__(self, db_session: AsyncSession):
        super().__init__(User, db_session)

    async def get_by_email(self, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        stmt = select(User).where(User.email == email)
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        stmt = select(User).where(User.username == username)
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email_or_username(self, identifier: str) -> Optional[User]:
        """根据邮箱或用户名获取用户"""
        stmt = select(User).where(
            or_(User.email == identifier, User.username == identifier)
        )
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(
        self,
        query: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """搜索用户"""
        stmt = select(User).where(
            or_(
                User.email.ilike(f"%{query}%"),
                User.username.ilike(f"%{query}%"),
                User.full_name.ilike(f"%{query}%")
            )
        ).offset(skip).limit(limit)
        
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())

    async def update_last_login(self, user_id: str) -> None:
        """更新最后登录时间"""
        from datetime import datetime, timezone
        stmt = select(User).where(User.id == user_id)
        result = await self.db_session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            user.last_login_at = datetime.now(timezone.utc)
            await self.db_session.flush()

    async def update_password(self, user_id: str, hashed_password: str) -> bool:
        """更新密码"""
        stmt = select(User).where(User.id == user_id)
        result = await self.db_session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            user.hashed_password = hashed_password
            await self.db_session.flush()
            return True
        return False

    async def activate_user(self, user_id: str) -> bool:
        """激活用户"""
        stmt = select(User).where(User.id == user_id)
        result = await self.db_session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            user.is_active = True
            user.email_verified = True
            await self.db_session.flush()
            return True
        return False

    async def deactivate_user(self, user_id: str) -> bool:
        """停用用户"""
        stmt = select(User).where(User.id == user_id)
        result = await self.db_session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user:
            user.is_active = False
            await self.db_session.flush()
            return True
        return False

    async def get_users_by_tenant(
        self,
        tenant_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[User]:
        """获取租户下的用户"""
        stmt = select(User).where(User.tenant_id == tenant_id).offset(skip).limit(limit)
        result = await self.db_session.execute(stmt)
        return list(result.scalars().all())