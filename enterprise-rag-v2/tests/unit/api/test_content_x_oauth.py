import json
import importlib
from types import SimpleNamespace
from uuid import uuid4
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException

from api.schemas.content import XOAuthCompleteRequest

content_router = importlib.import_module("api.routers.content")


class FakeRedis:
    def __init__(self, value: str):
        self.value = value
        self.deleted_keys: list[str] = []

    async def getdel(self, key: str):
        self.deleted_keys.append(key)
        value, self.value = self.value, None
        return value

    async def setex(self, key: str, ttl: int, value: str):
        self.setex_args = (key, ttl, value)


class FakeDb:
    async def commit(self):
        return None


@pytest.mark.asyncio
async def test_start_x_oauth_creates_s256_pkce_state_without_tokens(monkeypatch):
    user_id = uuid4()
    tenant_id = uuid4()
    workspace_id = uuid4()
    fake_redis = FakeRedis("")

    class FakeAccess:
        async def _verify_workspace_access(self, workspace, tenant, user, is_superuser):
            assert workspace == workspace_id
            assert tenant == tenant_id
            assert user == user_id
            assert is_superuser is False

    class FakeCredentialService:
        def __init__(self, _db):
            self.access = FakeAccess()

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(content_router, "_x_oauth_redis", fake_get_redis)
    monkeypatch.setattr(content_router, "ContentCredentialService", FakeCredentialService)
    monkeypatch.setattr(content_router, "get_settings", lambda: SimpleNamespace(
        x_oauth_client_id="client-123",
        x_oauth_client_secret="",
        x_oauth_scopes="tweet.read users.read",
        x_oauth_redirect_uri="http://localhost:3000/platform-data",
    ))

    result = await content_router.start_x_oauth(
        workspace_id,
        {"sub": str(user_id), "tenant_id": str(tenant_id), "is_superuser": False},
        FakeDb(),
    )
    params = parse_qs(urlparse(result["data"]["url"]).query)

    assert params["client_id"] == ["client-123"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["redirect_uri"] == ["http://localhost:3000/platform-data"]
    assert fake_redis.setex_args[1] == 600
    state_payload = json.loads(fake_redis.setex_args[2])
    assert state_payload["user_id"] == str(user_id)
    assert state_payload["tenant_id"] == str(tenant_id)
    assert state_payload["workspace_id"] == str(workspace_id)
    assert state_payload["code_verifier"]
    assert "access_token" not in state_payload


@pytest.mark.asyncio
async def test_complete_x_oauth_consumes_state_binds_tenant_and_never_returns_token(monkeypatch):
    user_id = uuid4()
    tenant_id = uuid4()
    workspace_id = uuid4()
    state = "state-12345678901234567890"
    fake_redis = FakeRedis(json.dumps({
        "user_id": str(user_id),
        "tenant_id": str(tenant_id),
        "workspace_id": str(workspace_id),
        "redirect_uri": "http://localhost:3000/platform-data",
        "code_verifier": "verifier-value",
    }))

    class FakeProvider:
        async def exchange_code(self, **kwargs):
            assert kwargs["code_verifier"] == "verifier-value"
            return {"access_token": "must-not-leak", "refresh_token": "refresh", "expires_in": 3600}

        async def get_user(self, access_token):
            assert access_token == "must-not-leak"
            return {"id": "x-user-1", "username": "codex"}

    created: list[dict] = []

    class FakeAccess:
        async def _verify_workspace_access(self, *args, **kwargs):
            assert args[0] == workspace_id
            assert args[1] == tenant_id
            assert args[2] == user_id

    class FakeCredentialService:
        def __init__(self, _db):
            self.access = FakeAccess()

        async def create(self, **kwargs):
            created.append(kwargs)
            return {"id": "credential-1", "platform": kwargs["platform"], "name": kwargs["name"]}

    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(content_router, "_x_oauth_redis", fake_get_redis)
    monkeypatch.setattr(content_router, "_x_provider", lambda: FakeProvider())
    monkeypatch.setattr(content_router, "ContentCredentialService", FakeCredentialService)
    monkeypatch.setattr(content_router, "get_settings", lambda: SimpleNamespace(x_oauth_redirect_uri="http://localhost:3000/platform-data"))

    result = await content_router.complete_x_oauth(
        XOAuthCompleteRequest(code="authorization-code", state=state),
        {"sub": str(user_id), "tenant_id": str(tenant_id), "is_superuser": False},
        FakeDb(),
    )

    assert result["success"] is True
    assert "must-not-leak" not in json.dumps(result)
    assert created[0]["credentials"]["access_token"] == "must-not-leak"
    assert fake_redis.deleted_keys == [content_router._x_oauth_state_key(state)]

    with pytest.raises(HTTPException) as exc_info:
        await content_router.complete_x_oauth(
            XOAuthCompleteRequest(code="authorization-code", state=state),
            {"sub": str(user_id), "tenant_id": str(tenant_id), "is_superuser": False},
            FakeDb(),
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_complete_x_oauth_rejects_state_from_another_tenant(monkeypatch):
    user_id = uuid4()
    state_tenant = uuid4()
    current_tenant = uuid4()
    fake_redis = FakeRedis(json.dumps({
        "user_id": str(user_id),
        "tenant_id": str(state_tenant),
        "workspace_id": str(uuid4()),
        "redirect_uri": "http://localhost:3000/platform-data",
        "code_verifier": "verifier-value",
    }))
    async def fake_get_redis():
        return fake_redis

    monkeypatch.setattr(content_router, "_x_oauth_redis", fake_get_redis)

    with pytest.raises(HTTPException) as exc_info:
        await content_router.complete_x_oauth(
            XOAuthCompleteRequest(code="code", state="state-12345678901234567890"),
            {"sub": str(user_id), "tenant_id": str(current_tenant), "is_superuser": False},
            FakeDb(),
        )
    assert exc_info.value.status_code == 403
    assert "租户" in str(exc_info.value.detail)
