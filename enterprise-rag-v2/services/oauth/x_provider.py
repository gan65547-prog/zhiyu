"""X OAuth 2.0 PKCE provider.

This module is deliberately separate from the legacy enterprise-login OAuth
providers. Content-platform authorization must never return a provider token
to the browser; the router stores the resulting token through the encrypted
content credential service instead.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx


class XOAuthProvider:
    AUTHORIZE_URL = "https://twitter.com/i/oauth2/authorize"
    TOKEN_URL = "https://api.x.com/2/oauth2/token"
    USER_URL = "https://api.x.com/2/users/me"

    def __init__(self, *, client_id: str, client_secret: str = "", scopes: str = ""):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.scopes = " ".join(scopes.split())

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.scopes)

    def authorization_url(self, *, redirect_uri: str, state: str, code_challenge: str) -> str:
        if not self.configured:
            raise RuntimeError("X OAuth 尚未配置 Client ID 和 scopes")
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.scopes,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str) -> dict[str, Any]:
        if not self.configured:
            return {"error": "X OAuth 尚未配置 Client ID 和 scopes"}
        data = {
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
            "client_id": self.client_id,
        }
        auth = None
        if self.client_secret:
            auth = (self.client_id, self.client_secret)
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
                response = await client.post(
                    self.TOKEN_URL,
                    data=data,
                    auth=auth,
                    headers={"Accept": "application/json"},
                )
            if response.status_code >= 400:
                return {"error": f"HTTP {response.status_code}", "retryable": response.status_code >= 500}
            payload = response.json()
            if not payload.get("access_token"):
                return {"error": "X OAuth 未返回 access_token"}
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            return {"error": str(exc), "retryable": True}

    async def get_user(self, access_token: str) -> dict[str, Any]:
        token = str(access_token or "").strip()
        if not token:
            return {"error": "X OAuth access_token 为空"}
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
                response = await client.get(
                    self.USER_URL,
                    params={"user.fields": "id,name,username,profile_image_url"},
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
            if response.status_code >= 400:
                return {"error": f"HTTP {response.status_code}"}
            payload = response.json().get("data") or {}
            if not payload.get("id"):
                return {"error": "X OAuth 用户信息缺少 id"}
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            return {"error": str(exc)}
