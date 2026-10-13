"""
飞书OAuth提供商实现
"""

from typing import Dict, Any, Optional
import httpx
from urllib.parse import urlencode

from services.interfaces.oauth_service import OAuthProvider


class FeishuOAuthProvider(OAuthProvider):
    """飞书OAuth提供商"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        base_url: str = "https://open.feishu.cn"
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """获取飞书授权URL"""
        params = {
            "app_id": self.app_id,
            "redirect_uri": redirect_uri,
            "scope": "contact:user.base:readonly",
            "response_type": "code"
        }

        if state:
            params["state"] = state

        return f"{self.base_url}/open-apis/authen/v1/authorize?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """使用授权码换取访问令牌"""
        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.base_url}/open-apis/authen/v1/oidc/access_token",
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._get_app_access_token()}"
                }
            )

            if response.status_code == 200:
                return response.json()
            return {"error": f"HTTP {response.status_code}"}
        except httpx.HTTPError as e:
            return {"error": str(e)}

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """获取飞书用户信息"""
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.base_url}/open-apis/authen/v1/user_info",
                headers={"Authorization": f"Bearer {access_token}"}
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "provider": "feishu",
                    "provider_user_id": data.get("union_id", ""),
                    "username": data.get("name", ""),
                    "email": data.get("email", ""),
                    "avatar_url": data.get("avatar_url", ""),
                    "raw_data": data
                }
            return {"error": f"HTTP {response.status_code}"}
        except httpx.HTTPError as e:
            return {"error": str(e)}

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """刷新访问令牌"""
        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.base_url}/open-apis/authen/v1/oidc/refresh_access_token",
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token
                },
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._get_app_access_token()}"
                }
            )

            if response.status_code == 200:
                return response.json()
            return {"error": f"HTTP {response.status_code}"}
        except httpx.HTTPError as e:
            return {"error": str(e)}

    def _get_app_access_token(self) -> str:
        """获取应用访问令牌（简化实现）"""
        return ""


class WeChatWorkOAuthProvider(OAuthProvider):
    """企业微信OAuth提供商"""

    def __init__(
        self,
        corp_id: str,
        agent_id: str,
        corp_secret: str,
        base_url: str = "https://qyapi.weixin.qq.com"
    ):
        self.corp_id = corp_id
        self.agent_id = agent_id
        self.corp_secret = corp_secret
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """获取企业微信授权URL"""
        params = {
            "appid": self.corp_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "snsapi_privateinfo",
            "state": state or ""
        }

        return f"{self.base_url}/cgi-bin/getcallbackurl?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """使用授权码换取访问令牌"""
        client = await self._get_client()

        try:
            access_token = await self._get_corp_access_token()

            response = await client.get(
                f"{self.base_url}/cgi-bin/auth/getuserinfo",
                params={
                    "access_token": access_token,
                    "code": code
                }
            )

            if response.status_code == 200:
                return response.json()
            return {"error": f"HTTP {response.status_code}"}
        except httpx.HTTPError as e:
            return {"error": str(e)}

    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """获取企业微信用户信息"""
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.base_url}/cgi-bin/auth/getuserdetail",
                params={"access_token": access_token},
                json={}
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    "provider": "wechat_work",
                    "provider_user_id": data.get("userid", ""),
                    "username": data.get("name", ""),
                    "email": data.get("email", ""),
                    "avatar_url": data.get("avatar", ""),
                    "raw_data": data
                }
            return {"error": f"HTTP {response.status_code}"}
        except httpx.HTTPError as e:
            return {"error": str(e)}

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """刷新访问令牌（企业微信不支持此操作）"""
        return {"error": "WeChat Work does not support token refresh"}

    async def _get_corp_access_token(self) -> str:
        """获取企业访问令牌"""
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.base_url}/cgi-bin/gettoken",
                params={
                    "corpid": self.corp_id,
                    "corpsecret": self.corp_secret
                }
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("access_token", "")
            return ""
        except httpx.HTTPError:
            return ""
