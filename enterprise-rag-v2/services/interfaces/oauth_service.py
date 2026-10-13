"""
OAuth服务接口定义

定义OAuth第三方登录的服务接口
"""

from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from uuid import UUID


class OAuthProvider(ABC):
    """OAuth提供商抽象接口"""

    @abstractmethod
    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """获取授权URL"""
        pass

    @abstractmethod
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """使用授权码换取访问令牌"""
        pass

    @abstractmethod
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """获取用户信息"""
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """刷新访问令牌"""
        pass


class OAuthServiceInterface(ABC):
    """OAuth服务接口"""

    @abstractmethod
    async def authenticate_with_oauth(
        self,
        provider: str,
        code: str,
        redirect_uri: str
    ) -> Dict[str, Any]:
        """使用OAuth认证"""
        pass

    @abstractmethod
    async def link_oauth_account(
        self,
        user_id: UUID,
        provider: str,
        provider_user_id: str
    ) -> bool:
        """关联OAuth账户"""
        pass

    @abstractmethod
    async def unlink_oauth_account(
        self,
        user_id: UUID,
        provider: str
    ) -> bool:
        """取消OAuth关联"""
        pass

    @abstractmethod
    async def get_linked_accounts(self, user_id: UUID) -> list:
        """获取用户关联的OAuth账户"""
        pass
