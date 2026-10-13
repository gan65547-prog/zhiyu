"""
用户服务接口

定义用户管理相关的业务逻辑接口
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from uuid import UUID
from core.value_objects.pagination import Pagination, Page


class UserService(ABC):
    """用户服务抽象接口"""
    
    @abstractmethod
    async def list_users(
        self,
        tenant_id: UUID,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        workspace_id: Optional[UUID] = None
    ) -> Page:
        """
        获取租户的用户列表
        
        Args:
            tenant_id: 租户ID
            page: 页码
            page_size: 每页数量
            search: 搜索关键词（用户名/邮箱）
            is_active: 过滤激活状态
            workspace_id: 过滤工作空间成员
            
        Returns:
            分页的用户列表
        """
        pass
    
    @abstractmethod
    async def create_user(
        self,
        tenant_id: UUID,
        username: str,
        email: str,
        password: str,
        is_active: bool = True,
        workspace_ids: Optional[List[UUID]] = None,
        default_role: str = "member"
    ) -> dict:
        """
        创建新用户
        
        Args:
            tenant_id: 租户ID
            username: 用户名
            email: 邮箱
            password: 密码
            is_active: 是否激活
            workspace_ids: 自动加入的工作空间ID列表
            default_role: 默认角色
            
        Returns:
            用户信息字典
        """
        pass
    
    @abstractmethod
    async def get_user(
        self,
        user_id: UUID
    ) -> Optional[dict]:
        """
        获取用户详情
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户信息字典或None
        """
        pass
    
    @abstractmethod
    async def update_user(
        self,
        user_id: UUID,
        username: Optional[str] = None,
        email: Optional[str] = None,
        is_active: Optional[bool] = None,
        extra_metadata: Optional[dict] = None
    ) -> dict:
        """
        更新用户信息
        
        Args:
            user_id: 用户ID
            username: 用户名
            email: 邮箱
            is_active: 是否激活
            extra_metadata: 扩展元数据
            
        Returns:
            更新后的用户信息
        """
        pass
    
    @abstractmethod
    async def delete_user(
        self,
        user_id: UUID
    ) -> bool:
        """
        删除用户
        
        Args:
            user_id: 用户ID
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def reset_password(
        self,
        user_id: UUID,
        new_password: str,
        send_email: bool = False
    ) -> dict:
        """
        重置用户密码
        
        Args:
            user_id: 用户ID
            new_password: 新密码
            send_email: 是否发送邮件通知
            
        Returns:
            结果字典
        """
        pass
    
    @abstractmethod
    async def activate_user(
        self,
        user_id: UUID,
        is_active: bool
    ) -> dict:
        """
        激活/停用用户
        
        Args:
            user_id: 用户ID
            is_active: true=激活, false=停用
            
        Returns:
            更新后的用户信息
        """
        pass
    
    @abstractmethod
    async def get_user_workspaces(
        self,
        user_id: UUID
    ) -> List[dict]:
        """
        获取用户的工作空间列表
        
        Args:
            user_id: 用户ID
            
        Returns:
            工作空间列表
        """
        pass
