from uuid import uuid4

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import Base, Tenant, User, Workspace, WorkspaceMember
from services.impl.content_credential_service import ContentCredentialService, CredentialVault
import services.impl.content_connector_registry as connector_module


@pytest_asyncio.fixture
async def credential_context():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        tenant = Tenant(name="Credential tenant", contact_email=f"{uuid4()}@example.com")
        user = User(tenant=tenant, username=f"credential-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
        workspace = Workspace(tenant=tenant, name="Credential workspace")
        session.add_all([tenant, user, workspace])
        await session.flush()
        session.add(WorkspaceMember(workspace=workspace, user=user))
        await session.flush()
        yield session, tenant, user, workspace
    await engine.dispose()


@pytest.mark.asyncio
async def test_credentials_are_encrypted_and_never_returned(credential_context):
    session, tenant, user, workspace = credential_context
    vault = CredentialVault(Fernet.generate_key())
    service = ContentCredentialService(session, vault=vault)
    safe = await service.create(
        workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        platform="wechat", name="official", credentials={"app_secret": "do-not-return"}, hint="末四位 ****",
    )
    assert "do-not-return" not in str(safe)
    assert (await service.list(workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id, is_superuser=False))[0]["credential_hint"] == "末四位 ****"
    resolved = await service.resolve(credential_id=str(safe["id"]), workspace_id=str(workspace.id), tenant_id=str(tenant.id))
    assert resolved is not None
    assert resolved[1]["app_secret"] == "do-not-return"
    revoked = await service.revoke(credential_id=safe["id"], tenant_id=tenant.id, user_id=user.id, is_superuser=False)
    assert revoked["status"] == "revoked"
    assert await service.resolve(credential_id=str(safe["id"]), workspace_id=str(workspace.id), tenant_id=str(tenant.id)) is None


@pytest.mark.asyncio
async def test_x_credential_test_calls_fixed_profile_endpoint_without_returning_token(monkeypatch, credential_context):
    session, tenant, user, workspace = credential_context
    vault = CredentialVault(Fernet.generate_key())
    service = ContentCredentialService(session, vault=vault)
    safe = await service.create(
        workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        platform="x", name="x-user", credentials={"access_token": "secret-token"}, hint="OAuth 已配置",
    )
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"data": {"id": "user-42"}}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, *, headers):
            captured.update({"url": url, "headers": headers})
            return FakeResponse()

    monkeypatch.setattr(connector_module.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    result = await service.test(
        credential_id=safe["id"], workspace_id=workspace.id, tenant_id=tenant.id,
        user_id=user.id, is_superuser=False,
    )

    assert result["status"] == "configured"
    assert result["message"] == "X OAuth 用户凭据验证通过"
    assert "external_user_id" not in result
    assert captured["url"] == "https://api.x.com/2/users/me"
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert "secret-token" not in str(result)
