"""
认证服务接口

定义用户认证和授权相关的业务逻辑接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple
from uuid import UUID
from datetime import datetime


class AuthService(ABC):
    """认证服务抽象接口"""
    
    @abstractmethod
    async def register(
        self,
        username: str,
        email: str,
        password: str,
        tenant_id: Optional[UUID] = None
    ) -> dict:
        """
        用户注册
        
        Args:
            username: 用户名
            email: 邮箱
            password: 密码
            tenant_id: 租户ID（可选）
            
        Returns:
            用户信息字典
        """
        pass
    
    @abstractmethod
    async def login(
        self,
        username: str,
        password: str
    ) -> dict:
        """
        用户登录
        
        Args:
            username: 用户名或邮箱
            password: 密码
            
        Returns:
            包含access_token和refresh_token的字典
        """
        pass
    
    @abstractmethod
    async def refresh_token(
        self,
        refresh_token: str
    ) -> dict:
        """
        刷新访问令牌
        
        Args:
            refresh_token: 刷新令牌
            
        Returns:
            新的access_token和refresh_token
        """
        pass
    
    @abstractmethod
    async def logout(
        self,
        user_id: UUID,
        access_token: str
    ) -> bool:
        """
        用户登出
        
        Args:
            user_id: 用户ID
            access_token: 访问令牌
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def verify_token(
        self,
        token: str
    ) -> Optional[dict]:
        """
        验证令牌
        
        Args:
            token: 访问令牌
            
        Returns:
            令牌payload或None
        """
        pass
    
    @abstractmethod
    async def change_password(
        self,
        user_id: UUID,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        修改密码
        
        Args:
            user_id: 用户ID
            old_password: 旧密码
            new_password: 新密码
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def reset_password(
        self,
        email: str
    ) -> bool:
        """
        重置密码（发送重置邮件）
        
        Args:
            email: 邮箱
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    async def verify_permission(
        self,
        user_id: UUID,
        resource_type: str,
        resource_id: UUID,
        action: str
    ) -> bool:
        """
        验证权限
        
        Args:
            user_id: 用户ID
            resource_type: 资源类型
            resource_id: 资源ID
            action: 操作类型
            
        Returns:
            是否有权限
        """
        pass
