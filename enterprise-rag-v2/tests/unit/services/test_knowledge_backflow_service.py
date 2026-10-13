import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import (
    Base,
    Dataset,
    Document,
    DocumentChunk,
    DocumentStatus,
    DocumentType,
    KnowledgeEvidence,
    KnowledgeItem,
    Tenant,
    User,
    Workspace,
    WorkspaceMember,
)
from services.impl.knowledge_backflow_service import (
    BACKFLOW_DATASET_NAME,
    DEFAULT_EMBEDDING_MODEL,
    KnowledgeBackflowService,
    card_file_name,
    render_card_markdown,
)
from services.impl.knowledge_service import KnowledgeService


@pytest.fixture
async def backflow_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


class FakeIndexingService:
    def __init__(self):
        self.deleted = []

    async def delete_document_vectors(self, document_id, workspace_id=None):
        self.deleted.append((str(document_id), workspace_id))
        return True


@pytest.fixture
def fake_celery(monkeypatch):
    fake = SimpleNamespace()
    fake.calls = []

    def apply_async(args=None, queue=None):
        fake.calls.append((args, queue))

    fake.process_document_task = SimpleNamespace(apply_async=apply_async)
    monkeypatch.setitem(sys.modules, "infrastructure.queue.document_tasks", fake)
    return fake


async def _identity(session: AsyncSession):
    tenant = Tenant(name="Backflow tenant", contact_email=f"{uuid4()}@example.com")
    user = User(
        tenant=tenant, username=f"backflow-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash"
    )
    workspace = Workspace(tenant=tenant, name="Backflow workspace")
    session.add_all([tenant, user, workspace])
    await session.flush()
    session.add(WorkspaceMember(workspace=workspace, user=user, role="member"))
    await session.flush()
    return tenant, user, workspace


async def _card(session: AsyncSession, tenant, user, workspace) -> KnowledgeItem:
    item = KnowledgeItem(
        tenant_id=str(tenant.id),
        workspace_id=str(workspace.id),
        created_by=str(user.id),
        title="行业增长结论",
        item_type="conclusion",
        definition="行业规模持续增长",
        details="近三年复合增速 15% 以上",
        conclusions=["行业处于上升期", "头部集中度提高"],
        confidence=0.8,
    )
    session.add(item)
    await session.flush()
    return item


def test_render_card_markdown_contains_sections():
    item = KnowledgeItem(
        id=str(uuid4()), title="结论卡片", item_type="conclusion",
        definition="定义内容", details="详情内容",
        conclusions=["结论一", "结论二"], confidence=0.9,
        extra_metadata={"origin": "research"},
    )
    evidence = SimpleNamespace(quote="原文引用片段", locator="p12")
    markdown = render_card_markdown(item, evidence=[evidence])

    assert "# 结论卡片" in markdown
    assert "## 定义" in markdown and "定义内容" in markdown
    assert "## 结论" in markdown and "- 结论一" in markdown
    assert "> 原文引用片段（p12）" in markdown
    assert '"origin": "research"' in markdown


@pytest.mark.asyncio
async def test_sync_creates_document_in_system_dataset(backflow_session, fake_celery, monkeypatch, tmp_path):
    monkeypatch.setenv("KNOWLEDGE_BACKFLOW_ENABLED", "1")
    monkeypatch.chdir(tmp_path)
    tenant, user, workspace = await _identity(backflow_session)
    item = await _card(backflow_session, tenant, user, workspace)
    service = KnowledgeBackflowService(backflow_session)

    result = await service.sync_to_rag(item)

    assert result["action"] == "created"
    dataset = (
        await backflow_session.execute(
            select(Dataset).where(Dataset.workspace_id == str(workspace.id), Dataset.name == BACKFLOW_DATASET_NAME)
        )
    ).scalar_one()
    assert dataset.extra_metadata["is_system"] is True
    document = (
        await backflow_session.execute(select(Document).where(Document.dataset_id == str(dataset.id)))
    ).scalar_one()
    assert document.file_name == card_file_name(item.id)
    assert document.extra_metadata["source"] == "knowledge_card"
    assert document.extra_metadata["knowledge_item_id"] == str(item.id)
    assert fake_celery.calls == [([str(document.id)], "documents_high")]


@pytest.mark.asyncio
async def test_sync_is_idempotent_on_reapproval(backflow_session, fake_celery, monkeypatch, tmp_path):
    monkeypatch.setenv("KNOWLEDGE_BACKFLOW_ENABLED", "1")
    monkeypatch.chdir(tmp_path)
    tenant, user, workspace = await _identity(backflow_session)
    item = await _card(backflow_session, tenant, user, workspace)
    service = KnowledgeBackflowService(backflow_session)

    first = await service.sync_to_rag(item)
    item.conclusions = ["行业处于上升期", "头部集中度提高", "新增第三条结论"]
    second = await service.sync_to_rag(item)

    assert first["action"] == "created"
    assert second["action"] == "updated"
    assert second["document_id"] == first["document_id"]
    documents = (
        (await backflow_session.execute(select(Document).where(Document.file_name == card_file_name(item.id))))
        .scalars()
        .all()
    )
    assert len(documents) == 1
    assert documents[0].status == DocumentStatus.PENDING
    content = Path(service._card_file_path(item.id)).read_text(encoding="utf-8")
    assert "新增第三条结论" in content


@pytest.mark.asyncio
async def test_remove_from_rag_deletes_vectors_chunks_and_document(backflow_session, fake_celery, monkeypatch, tmp_path):
    monkeypatch.setenv("KNOWLEDGE_BACKFLOW_ENABLED", "1")
    monkeypatch.chdir(tmp_path)
    tenant, user, workspace = await _identity(backflow_session)
    item = await _card(backflow_session, tenant, user, workspace)
    service = KnowledgeBackflowService(backflow_session)
    created = await service.sync_to_rag(item)

    chunk = DocumentChunk(
        document_id=str(created["document_id"]),
        chunk_index=0,
        content="片段",
    )
    backflow_session.add(chunk)
    await backflow_session.flush()

    fake_indexing = FakeIndexingService()
    removal = KnowledgeBackflowService(
        backflow_session, document_service=service.document_service, indexing_service=fake_indexing
    )
    await removal.remove_from_rag(item)

    assert fake_indexing.deleted == [(str(created["document_id"]), str(workspace.id))]
    assert (
        await backflow_session.execute(select(Document).where(Document.id == str(created["document_id"])))
    ).scalar_one_or_none() is None
    assert (
        await backflow_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == str(created["document_id"]))
        )
    ).scalar_one_or_none() is None

    await removal.remove_from_rag(item)
    assert len(fake_indexing.deleted) == 1


@pytest.mark.asyncio
async def test_hooks_noop_when_disabled(backflow_session, monkeypatch):
    monkeypatch.delenv("KNOWLEDGE_BACKFLOW_ENABLED", raising=False)
    tenant, user, workspace = await _identity(backflow_session)
    item = await _card(backflow_session, tenant, user, workspace)
    service = KnowledgeBackflowService(backflow_session)

    assert await service.sync_to_rag(item) is None
    assert await service.remove_from_rag(item) is None
    datasets = (
        (await backflow_session.execute(select(Dataset).where(Dataset.name == BACKFLOW_DATASET_NAME)))
        .scalars()
        .all()
    )
    assert datasets == []


@pytest.mark.asyncio
async def test_review_approval_triggers_backflow(backflow_session, fake_celery, monkeypatch, tmp_path):
    monkeypatch.setenv("KNOWLEDGE_BACKFLOW_ENABLED", "1")
    monkeypatch.chdir(tmp_path)
    tenant, user, workspace = await _identity(backflow_session)
    service = KnowledgeService(backflow_session)
    created = await service.create_item(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        workspace_id=workspace.id, title="有证据的卡片", item_type="concept",
        definition="带证据的定义", metadata={"source": "manual"},
    )
    dataset = Dataset(
        workspace_id=str(workspace.id), name=BACKFLOW_DATASET_NAME,
        embedding_model=DEFAULT_EMBEDDING_MODEL, extra_metadata={"is_system": True},
    )
    backflow_session.add(dataset)
    await backflow_session.flush()
    source_document = Document(
        dataset_id=str(dataset.id), file_name="来源.md", file_type=DocumentType.MD,
        file_size=128, file_path="/tmp/来源.md", status=DocumentStatus.COMPLETED,
    )
    backflow_session.add(source_document)
    await backflow_session.flush()
    await service.add_evidence(
        item_id=created["id"], tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        document_id=str(source_document.id), quote="证据引用原文",
    )
    backflow_session.add(source_document)

    reviewed = await service.review_item(
        item_id=created["id"], tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, review_status="approved",
    )

    assert reviewed["review_status"] == "approved"
    backflow_document = (
        await backflow_session.execute(
            select(Document).where(Document.file_name == card_file_name(created["id"]))
        )
    ).scalar_one()
    assert backflow_document.extra_metadata["knowledge_item_id"] == str(created["id"])
    assert fake_celery.calls and fake_celery.calls[0][1] == "documents_high"


@pytest.mark.asyncio
async def test_review_to_draft_removes_backflow_document(backflow_session, fake_celery, monkeypatch, tmp_path):
    monkeypatch.setenv("KNOWLEDGE_BACKFLOW_ENABLED", "1")
    monkeypatch.chdir(tmp_path)
    tenant, user, workspace = await _identity(backflow_session)
    service = KnowledgeService(backflow_session)
    created = await service.create_item(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        workspace_id=workspace.id, title="回流后退回的卡片", item_type="concept",
        definition="退回场景定义",
    )
    dataset = Dataset(
        workspace_id=str(workspace.id), name=BACKFLOW_DATASET_NAME,
        embedding_model=DEFAULT_EMBEDDING_MODEL, extra_metadata={"is_system": True},
    )
    backflow_session.add(dataset)
    await backflow_session.flush()
    source_document = Document(
        dataset_id=str(dataset.id), file_name="来源.md", file_type=DocumentType.MD,
        file_size=128, file_path="/tmp/来源.md", status=DocumentStatus.COMPLETED,
    )
    backflow_session.add(source_document)
    await backflow_session.flush()
    await service.add_evidence(
        item_id=created["id"], tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        document_id=str(source_document.id), quote="证据引用原文",
    )
    backflow_session.add(source_document)

    await service.review_item(
        item_id=created["id"], tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, review_status="approved",
    )
    fake_celery.calls.clear()

    await service.review_item(
        item_id=created["id"], tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, review_status="draft",
    )

    remaining = (
        await backflow_session.execute(
            select(Document).where(Document.file_name == card_file_name(created["id"]))
        )
    ).scalar_one_or_none()
    assert remaining is None
    assert fake_celery.calls == []
