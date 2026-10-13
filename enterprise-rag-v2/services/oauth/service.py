"""
OAuth服务实现
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
import secrets
import httpx

from core.config import get_settings
from services.interfaces.oauth_service import OAuthServiceInterface
from services.oauth.providers import FeishuOAuthProvider, WeChatWorkOAuthProvider


class OAuthServiceImpl(OAuthServiceInterface):
    """OAuth服务实现"""

    def __init__(self):
        self.settings = get_settings()
        self._providers: Dict[str, Any] = {}
        self._init_providers()

    def _init_providers(self):
        """初始化OAuth提供商"""
        feishu_config = self.settings.oauth.get("feishu") if hasattr(self.settings, 'oauth') else None
        if feishu_config:
            self._providers["feishu"] = FeishuOAuthProvider(
                app_id=feishu_config.get("app_id", ""),
                app_secret=feishu_config.get("app_secret", "")
            )

        wechat_config = self.settings.oauth.get("wechat_work") if hasattr(self.settings, 'oauth') else None
        if wechat_config:
            self._providers["wechat_work"] = WeChatWorkOAuthProvider(
                corp_id=wechat_config.get("corp_id", ""),
                agent_id=wechat_config.get("agent_id", ""),
                corp_secret=wechat_config.get("corp_secret", "")
            )

    def get_provider(self, provider: str):
        """获取OAuth提供商"""
        return self._providers.get(provider)

    async def authenticate_with_oauth(
        self,
        provider: str,
        code: str,
        redirect_uri: str
    ) -> Dict[str, Any]:
        """使用OAuth认证"""
        oauth_provider = self.get_provider(provider)
        if not oauth_provider:
            raise ValueError(f"Unsupported OAuth provider: {provider}")

        token_result = await oauth_provider.exchange_code_for_token(code, redirect_uri)
        if "error" in token_result:
            raise ValueError(f"Token exchange failed: {token_result.get('error')}")

        access_token = token_result.get("data", {}).get("access_token")
        if not access_token:
            raise ValueError("No access token received")

        user_info = await oauth_provider.get_user_info(access_token)
        if "error" in user_info:
            raise ValueError(f"Failed to get user info: {user_info.get('error')}")

        return {
            "provider": provider,
            "provider_user_id": user_info.get("provider_user_id"),
            "username": user_info.get("username"),
            "email": user_info.get("email"),
            "avatar_url": user_info.get("avatar_url"),
            "access_token": access_token,
            "refresh_token": token_result.get("data", {}).get("refresh_token"),
            "expires_in": token_result.get("data", {}).get("expires_in")
        }

    async def link_oauth_account(
        self,
        user_id: UUID,
        provider: str,
        provider_user_id: str
    ) -> bool:
        """关联OAuth账户"""
        return True

    async def unlink_oauth_account(
        self,
        user_id: UUID,
        provider: str
    ) -> bool:
        """取消OAuth关联"""
        return True

    async def get_linked_accounts(self, user_id: UUID) -> List[Dict[str, Any]]:
        """获取用户关联的OAuth账户"""
        return []

    def generate_state(self) -> str:
        """生成OAuth状态参数"""
        return secrets.token_urlsafe(32)


class OAuthServiceFactory:
    """OAuth服务工厂"""

    _instance: Optional[OAuthServiceImpl] = None

    @classmethod
    def get_instance(cls) -> OAuthServiceImpl:
        """获取OAuth服务实例"""
        if cls._instance is None:
            cls._instance = OAuthServiceImpl()
        return cls._instance
