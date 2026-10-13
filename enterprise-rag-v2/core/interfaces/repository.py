"""
Repository 抽象接口

定义数据访问层的抽象接口，遵循Repository模式
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Dict, Any
from uuid import UUID

from ..entities.base import BaseEntity
from ..value_objects.pagination import Pagination, Page

T = TypeVar('T', bound=BaseEntity)


class Repository(ABC, Generic[T]):
    """通用Repository接口"""
    
    @abstractmethod
    async def create(self, entity: T) -> T:
        """创建实体"""
        pass
    
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Optional[T]:
        """根据ID获取实体"""
        pass
    
    @abstractmethod
    async def update(self, entity: T) -> T:
        """更新实体"""
        pass
    
    @abstractmethod
    async def delete(self, id: UUID) -> bool:
        """删除实体"""
        pass
    
    @abstractmethod
    async def list(self, 
                  filters: Dict[str, Any] = None, 
                  pagination: Pagination = None) -> Page:
        """分页查询实体列表"""
        pass
    
    @abstractmethod
    async def exists(self, id: UUID) -> bool:
        """检查实体是否存在"""
        pass
    
    @abstractmethod
    async def batch_create(self, entities: List[T]) -> List[T]:
        """
        批量创建实体
        
        Args:
            entities: 实体列表
            
        Returns:
            创建后的实体列表
        """
        pass
    
    @abstractmethod
    async def batch_update(self, entities: List[T]) -> List[T]:
        """
        批量更新实体
        
        Args:
            entities: 实体列表
            
        Returns:
            更新后的实体列表
        """
        pass
    
    @abstractmethod
    async def batch_delete(self, ids: List[UUID]) -> int:
        """
        批量删除实体
        
        Args:
            ids: 实体ID列表
            
        Returns:
            删除的数量
        """
        pass
    
    @abstractmethod
    async def batch_get(self, ids: List[UUID]) -> List[T]:
        """
        批量获取实体
        
        Args:
            ids: 实体ID列表
            
        Returns:
            实体列表
        """
        pass


class TenantRepository(Repository[T]):
    """租户相关Repository接口"""
    
    @abstractmethod
    async def get_by_tenant_id(self, tenant_id: UUID, id: UUID) -> Optional[T]:
        """根据租户ID和实体ID获取实体"""
        pass
    
    @abstractmethod
    async def list_by_tenant(self, 
                            tenant_id: UUID,
                            filters: Dict[str, Any] = None,
                            pagination: Pagination = None) -> Page:
        """根据租户ID分页查询实体列表"""
        pass


class WorkspaceRepository(Repository[T]):
    """工作空间相关Repository接口"""
    
    @abstractmethod
    async def get_by_workspace_id(self, workspace_id: UUID, id: UUID) -> Optional[T]:
        """根据工作空间ID和实体ID获取实体"""
        pass
    
    @abstractmethod
    async def list_by_workspace(self, 
                               workspace_id: UUID,
                               filters: Dict[str, Any] = None,
                               pagination: Pagination = None) -> Page:
        """根据工作空间ID分页查询实体列表"""
        pass