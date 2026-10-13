from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import (
    Base,
    ContentConnectorCredential,
    ContentDraft,
    ContentMetric,
    ContentMetricSyncRun,
    ContentPublishRecord,
    Tenant,
    User,
    Workspace,
    WorkspaceMember,
)
from services.impl.content_metric_sync_service import ContentMetricSyncService
import services.impl.content_connector_registry as connector_module


@pytest_asyncio.fixture
async def sync_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_x_metric_sync_reads_connector_metrics_into_content_metric(sync_session, monkeypatch):
    tenant = Tenant(name="Metric tenant", contact_email=f"{uuid4()}@example.com")
    user = User(tenant=tenant, username=f"metric-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
    workspace = Workspace(tenant=tenant, name="Metric workspace")
    sync_session.add_all([tenant, user, workspace])
    await sync_session.flush()
    sync_session.add(WorkspaceMember(workspace=workspace, user=user))
    draft = ContentDraft(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="X 帖子", body="正文", review_status="approved")
    credential = ContentConnectorCredential(
        tenant_id=tenant.id, workspace_id=workspace.id, platform="x", name="x-user",
        encrypted_credentials="test-encrypted", credential_hint="已配置", created_by=user.id,
    )
    sync_session.add_all([draft, credential])
    await sync_session.flush()
    record = ContentPublishRecord(
        tenant_id=tenant.id, workspace_id=workspace.id, draft_id=draft.id, platform="x",
        credential_id=credential.id, status="published", external_id="123456789",
        published_at=datetime.now(timezone.utc),
    )
    run = ContentMetricSyncRun(
        tenant_id=tenant.id, workspace_id=workspace.id, credential_id=credential.id, platform="x",
        requested_by=user.id, status="queued", payload_json={"items": []},
    )
    sync_session.add_all([record, run])
    await sync_session.flush()

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"data": {"id": "123456789", "public_metrics": {"impression_count": 1000, "like_count": 40, "reply_count": 5, "retweet_count": 7, "quote_count": 2}}}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, *, headers, params):
            assert url == "https://api.x.com/2/tweets/123456789"
            return FakeResponse()

    monkeypatch.setattr(connector_module.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    service = ContentMetricSyncService(sync_session)
    service.credentials.resolve = lambda **kwargs: _resolved_credential()

    result = await service.execute(run_id=str(run.id))
    assert result["status"] == "completed"
    assert result["inserted"] == 1
    metric = await sync_session.scalar(select(ContentMetric).where(ContentMetric.publish_record_id == str(record.id)))
    assert metric is not None
    assert metric.impressions == 1000


async def _resolved_credential():
    return SimpleNamespace(id="credential"), {"access_token": "token"}
