"""
基础实体类

定义所有实体的基类
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import Optional


class BaseEntity:
    """基础实体类"""
    
    def __init__(self, 
                 id: Optional[UUID] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        self.id = id or uuid4()
        self.created_at = created_at or datetime.now(timezone.utc)
        self.updated_at = updated_at or datetime.now(timezone.utc)
    
    def update_timestamp(self) -> None:
        """更新时间戳"""
        self.updated_at = datetime.now(timezone.utc)
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, BaseEntity):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        return hash(self.id)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id})"


class TenantEntity(BaseEntity):
    """租户相关实体基类"""
    
    def __init__(self, 
                 tenant_id: UUID,
                 id: Optional[UUID] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        super().__init__(id, created_at, updated_at)
        self.tenant_id = tenant_id


class WorkspaceEntity(TenantEntity):
    """工作空间相关实体基类"""
    
    def __init__(self, 
                 tenant_id: UUID,
                 workspace_id: UUID,
                 id: Optional[UUID] = None,
                 created_at: Optional[datetime] = None,
                 updated_at: Optional[datetime] = None):
        super().__init__(tenant_id, id, created_at, updated_at)
        self.workspace_id = workspace_id