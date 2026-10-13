from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import Asset, AssetStatus, Base, Dataset, Document, Tenant, User, Workspace, WorkspaceMember
from infrastructure.storage.asset_storage import LocalAssetStorage
from services.impl.asset_service import AssetServiceImpl
from services.impl.asset_ingestion_service import AssetIngestionService
from services.impl.safe_fetcher import FetchedResource


class StubFetcher:
    async def fetch(self, url: str) -> FetchedResource:
        return FetchedResource(
            url=url,
            content=b"<html><body>deterministic URL fixture</body></html>",
            content_type="text/html",
        )


class FlakyFetcher:
    def __init__(self):
        self.calls = 0

    async def fetch(self, url: str) -> FetchedResource:
        self.calls += 1
        if self.calls == 1:
            raise httpx.ReadTimeout("temporary upstream timeout")
        return FetchedResource(url=url, content=b"retry succeeded", content_type="text/plain")


@pytest.fixture
async def asset_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_asset_lifecycle_is_scoped_to_workspace(asset_session):
    tenant = Tenant(name="Tenant", contact_email="tenant@example.com")
    user = User(
        tenant=tenant,
        username=f"user-{uuid4()}",
        email=f"{uuid4()}@example.com",
        hashed_password="hash",
    )
    workspace = Workspace(tenant=tenant, name="Workspace")
    asset_session.add_all([tenant, user, workspace])
    await asset_session.flush()
    asset_session.add(WorkspaceMember(workspace=workspace, user=user, role="member"))
    await asset_session.flush()

    service = AssetServiceImpl(asset_session)
    created = await service.create_asset(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        source_type="url",
        title="Industry brief",
        source_uri="https://example.com/brief",
    )
    assert created["status"] == "pending"

    processing = await service.processing_status(
        asset_id=UUID(created["id"]), tenant_id=tenant.id, user_id=user.id
    )
    assert processing["status"] == AssetStatus.PENDING.value
    assert processing["progress"] == 0

    listed = await service.list_assets(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
    )
    assert listed["total"] == 1
    assert listed["items"][0]["id"] == created["id"]

    assert await service.delete_asset(
        asset_id=created["id"],
        tenant_id=tenant.id,
        user_id=user.id,
    )
    assert (await service.list_assets(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
    ))["total"] == 0


@pytest.mark.asyncio
async def test_failed_asset_can_be_reset_for_retry(asset_session):
    tenant = Tenant(name="Tenant", contact_email="retry@example.com")
    user = User(
        tenant=tenant,
        username=f"user-{uuid4()}",
        email=f"{uuid4()}@example.com",
        hashed_password="hash",
    )
    workspace = Workspace(tenant=tenant, name="Workspace")
    asset_session.add_all([tenant, user, workspace])
    await asset_session.flush()
    asset_session.add(WorkspaceMember(workspace=workspace, user=user, role="member"))
    await asset_session.flush()
    service = AssetServiceImpl(asset_session)
    created = await service.create_asset(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        source_type="url",
        title="Retry me",
        source_uri="https://example.com/retry",
    )
    asset = await asset_session.get(Asset, UUID(created["id"]))
    asset.status = AssetStatus.FAILED.value
    asset.processing_error = "temporary failure"
    await asset_session.flush()

    retried = await service.prepare_retry(
        asset_id=UUID(created["id"]), tenant_id=tenant.id, user_id=user.id
    )
    assert retried["status"] == AssetStatus.PENDING.value
    assert retried["metadata"]["retry_count"] == 1
    assert retried["processing_error"] is None


@pytest.mark.asyncio
async def test_asset_url_requires_source_uri(asset_session):
    tenant = Tenant(name="Tenant", contact_email="tenant@example.com")
    user = User(
        tenant=tenant,
        username=f"user-{uuid4()}",
        email=f"{uuid4()}@example.com",
        hashed_password="hash",
    )
    workspace = Workspace(tenant=tenant, name="Workspace")
    asset_session.add_all([tenant, user, workspace])
    await asset_session.flush()
    asset_session.add(WorkspaceMember(workspace=workspace, user=user, role="member"))
    await asset_session.flush()

    with pytest.raises(ValueError, match="source_uri"):
        await AssetServiceImpl(asset_session).create_asset(
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            user_id=user.id,
            source_type="url",
            title="Missing URL",
        )


@pytest.mark.asyncio
async def test_asset_ingestion_creates_legacy_document(asset_session, tmp_path):
    tenant = Tenant(name="Tenant", contact_email="tenant@example.com")
    user = User(
        tenant=tenant,
        username=f"user-{uuid4()}",
        email=f"{uuid4()}@example.com",
        hashed_password="hash",
    )
    workspace = Workspace(tenant=tenant, name="Workspace")
    dataset = Dataset(
        workspace=workspace,
        name="Industry knowledge",
        embedding_model="test-model",
    )
    asset_session.add_all([tenant, user, workspace, dataset])
    await asset_session.flush()
    asset_session.add(WorkspaceMember(workspace=workspace, user=user, role="member"))
    await asset_session.flush()

    asset = await AssetServiceImpl(asset_session).create_asset(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        dataset_id=dataset.id,
        user_id=user.id,
        source_type="file",
        title="industry-notes.txt",
    )
    result = await AssetIngestionService(
        asset_session,
        storage=LocalAssetStorage(str(tmp_path)),
    ).ingest_bytes(
        asset_id=UUID(asset["id"]),
        tenant_id=tenant.id,
        user_id=user.id,
        content="行业知识内容".encode("utf-8"),
        content_type="text/plain",
    )

    assert result["status"] == "processing"
    assert result["document_id"] == result["legacy_document_id"]
    document = await asset_session.get(Document, UUID(result["document_id"]))
    assert document is not None
    assert document.dataset_id == dataset.id
    assert document.file_size == len("行业知识内容".encode("utf-8"))


@pytest.mark.asyncio
async def test_text_asset_ingestion_without_dataset_uses_default_dataset(asset_session, tmp_path):
    tenant = Tenant(name="Text tenant", contact_email="text@example.com")
    user = User(
        tenant=tenant,
        username=f"text-{uuid4()}",
        email=f"{uuid4()}@example.com",
        hashed_password="hash",
    )
    workspace = Workspace(tenant=tenant, name="Text workspace")
    asset_session.add_all([tenant, user, workspace])
    await asset_session.flush()
    asset_session.add(WorkspaceMember(workspace=workspace, user=user, role="member"))
    await asset_session.flush()

    asset = await AssetServiceImpl(asset_session).create_asset(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        source_type="text",
        title="粘贴的行业笔记",
    )
    result = await AssetIngestionService(
        asset_session,
        storage=LocalAssetStorage(str(tmp_path)),
    ).ingest_bytes(
        asset_id=UUID(asset["id"]),
        tenant_id=tenant.id,
        user_id=user.id,
        content="用户明确需要证据链。".encode("utf-8"),
        content_type="text/plain; charset=utf-8",
    )

    assert result["status"] == "processing"
    assert result["document_id"] is not None
    assert result["size_bytes"] > 0


@pytest.mark.asyncio
async def test_url_asset_ingestion_success_persists_fetched_content(asset_session, tmp_path):
    tenant = Tenant(name="URL tenant", contact_email="url@example.com")
    user = User(
        tenant=tenant,
        username=f"url-{uuid4()}",
        email=f"{uuid4()}@example.com",
        hashed_password="hash",
    )
    workspace = Workspace(tenant=tenant, name="URL workspace")
    asset_session.add_all([tenant, user, workspace])
    await asset_session.flush()
    asset_session.add(WorkspaceMember(workspace=workspace, user=user, role="member"))
    await asset_session.flush()

    asset = await AssetServiceImpl(asset_session).create_asset(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        source_type="url",
        title="公开测试页面",
        source_uri="https://fixture.example.test/page",
    )
    result = await AssetIngestionService(
        asset_session,
        fetcher=StubFetcher(),
        storage=LocalAssetStorage(str(tmp_path)),
    ).ingest_url(
        asset_id=UUID(asset["id"]),
        tenant_id=tenant.id,
        user_id=user.id,
    )

    assert result["status"] == "processing"
    assert result["document_id"] is not None
    assert result["mime_type"] == "text/html"
    assert result["size_bytes"] == len(b"<html><body>deterministic URL fixture</body></html>")
    assert result["storage_key"]
    assert result["content_hash"]


@pytest.mark.asyncio
async def test_url_asset_timeout_can_retry_to_success(asset_session, tmp_path):
    tenant = Tenant(name="Retry URL tenant", contact_email="retry-url@example.com")
    user = User(
        tenant=tenant,
        username=f"retry-url-{uuid4()}",
        email=f"{uuid4()}@example.com",
        hashed_password="hash",
    )
    workspace = Workspace(tenant=tenant, name="Retry URL workspace")
    asset_session.add_all([tenant, user, workspace])
    await asset_session.flush()
    asset_session.add(WorkspaceMember(workspace=workspace, user=user, role="member"))
    await asset_session.flush()

    asset = await AssetServiceImpl(asset_session).create_asset(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        user_id=user.id,
        source_type="url",
        title="可重试公网页面",
        source_uri="https://fixture.example.test/retry",
    )
    fetcher = FlakyFetcher()
    ingestion = AssetIngestionService(
        asset_session,
        fetcher=fetcher,
        storage=LocalAssetStorage(str(tmp_path)),
    )

    with pytest.raises(httpx.ReadTimeout, match="temporary upstream timeout"):
        await ingestion.ingest_url(
            asset_id=UUID(asset["id"]), tenant_id=tenant.id, user_id=user.id,
        )
    failed = await asset_session.get(Asset, UUID(asset["id"]))
    assert failed.status == AssetStatus.FAILED.value
    assert failed.processing_error == "temporary upstream timeout"

    retried = await AssetServiceImpl(asset_session).prepare_retry(
        asset_id=UUID(asset["id"]), tenant_id=tenant.id, user_id=user.id,
    )
    assert retried["status"] == AssetStatus.PENDING.value
    succeeded = await ingestion.ingest_url(
        asset_id=UUID(asset["id"]), tenant_id=tenant.id, user_id=user.id,
    )
    assert succeeded["status"] == AssetStatus.PROCESSING.value
    assert succeeded["document_id"] is not None
    assert succeeded["size_bytes"] == len(b"retry succeeded")
    assert fetcher.calls == 2
