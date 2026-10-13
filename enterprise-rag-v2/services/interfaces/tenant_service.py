"""
租户服务接口

定义租户管理相关的业务逻辑接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from uuid import UUID
from core.value_objects.pagination import Pagination, Page


class TenantService(ABC):
    """租户服务抽象接口"""
    
    @abstractmethod
    async def create_tenant(
        self,
        name: str,
        contact_email: str,
        contact_phone: Optional[str] = None,
        plan: str = "free",
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        """
        创建租户
        
        Args:
            name: 租户名称
            contact_email: 联系邮箱
            contact_phone: 联系电话
            plan: 订阅计划
            metadata: 元数据
            
        Returns:
            租户信息字典
        """
        pass
    
    @abstractmethod
    async def get_tenant(
        self,
        tenant_id: UUID
    ) -> Optional[dict]:
        """
        获取租户详情
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            租户信息字典或None
        """
        pass
    
    @abstractmethod
    async def update_tenant(
        self,
        tenant_id: UUID,
        name: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
        plan: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        """
        更新租户
        
        Args:
            tenant_id: 租户ID
            name: 租户名称
            contact_email: 联系邮箱
            contact_phone: 联系电话
            plan: 订阅计划
            status: 租户状态
            metadata: 元数据
            
        Returns:
            更新后的租户信息
        """
        pass
    
    @abstractmethod
    async def delete_tenant(
        self,
        tenant_id: UUID
    ) -> bool:
        """
        删除租户
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def list_tenants(
        self,
        status: Optional[str] = None,
        plan: Optional[str] = None,
        keyword: Optional[str] = None,
        pagination: Optional[Pagination] = None
    ) -> Page:
        """
        查询租户列表
        
        Args:
            status: 租户状态
            plan: 订阅计划
            keyword: 关键词搜索
            pagination: 分页参数
            
        Returns:
            分页的租户列表
        """
        pass
    
    @abstractmethod
    async def get_tenant_usage(
        self,
        tenant_id: UUID
    ) -> dict:
        """
        获取租户使用情况
        
        Args:
            tenant_id: 租户ID
            
        Returns:
            使用情况统计
        """
        pass
    
    @abstractmethod
    async def check_quota(
        self,
        tenant_id: UUID,
        resource_type: str
    ) -> bool:
        """
        检查配额是否充足
        
        Args:
            tenant_id: 租户ID
            resource_type: 资源类型
            
        Returns:
            是否有配额
        """
        pass
