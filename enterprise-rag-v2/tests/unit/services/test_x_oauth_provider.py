from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from services.oauth.x_provider import XOAuthProvider


def test_authorization_url_uses_pkce_and_fixed_x_endpoint():
    provider = XOAuthProvider(
        client_id="client-123",
        scopes="tweet.read users.read",
    )

    parsed = urlparse(provider.authorization_url(
        redirect_uri="http://localhost:3000/platform-data",
        state="state-1234567890123456",
        code_challenge="challenge-123",
    ))
    params = parse_qs(parsed.query)

    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == provider.AUTHORIZE_URL
    assert params["client_id"] == ["client-123"]
    assert params["redirect_uri"] == ["http://localhost:3000/platform-data"]
    assert params["state"] == ["state-1234567890123456"]
    assert params["code_challenge"] == ["challenge-123"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["scope"] == ["tweet.read users.read"]


@pytest.mark.asyncio
async def test_exchange_code_uses_pkce_form_without_leaking_secret(monkeypatch):
    calls: list[dict] = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, **kwargs):
            calls.append({"url": url, **kwargs})
            return httpx.Response(200, json={"access_token": "access-token", "refresh_token": "refresh-token", "expires_in": 7200})

    monkeypatch.setattr("services.oauth.x_provider.httpx.AsyncClient", lambda **_kwargs: FakeClient())
    provider = XOAuthProvider(client_id="client-123", client_secret="client-secret", scopes="tweet.read")

    result = await provider.exchange_code(
        code="authorization-code",
        redirect_uri="http://localhost:3000/platform-data",
        code_verifier="verifier-value",
    )

    assert result["access_token"] == "access-token"
    assert calls[0]["url"] == provider.TOKEN_URL
    assert calls[0]["data"]["code_verifier"] == "verifier-value"
    assert calls[0]["data"]["client_id"] == "client-123"
    assert calls[0]["auth"] == ("client-123", "client-secret")
    assert "access-token" not in calls[0]["url"]


@pytest.mark.asyncio
async def test_unconfigured_provider_fails_closed():
    provider = XOAuthProvider(client_id="", scopes="tweet.read")

    assert provider.configured is False
    with pytest.raises(RuntimeError, match="尚未配置"):
        provider.authorization_url(redirect_uri="http://localhost", state="state-1234567890123456", code_challenge="challenge")
    result = await provider.exchange_code(code="code", redirect_uri="http://localhost", code_verifier="verifier")
    assert result["error"]
