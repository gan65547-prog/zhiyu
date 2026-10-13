from datetime import datetime, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import Asset, Base, ContentDraft, ContentPublishRecord, KnowledgeItem, Tenant, User, Workspace, WorkspaceMember
from services.impl.workbench_service import WorkbenchService


@pytest_asyncio.fixture
async def workbench_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_workbench_search_is_workspace_scoped(workbench_session):
    tenant = Tenant(name="Search tenant", contact_email=f"{uuid4()}@example.com")
    user = User(tenant=tenant, username=f"search-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
    workspace = Workspace(tenant=tenant, name="Search workspace")
    other_workspace = Workspace(tenant=tenant, name="Other workspace")
    workbench_session.add_all([tenant, user, workspace, other_workspace])
    await workbench_session.flush()
    workbench_session.add_all([
        WorkspaceMember(workspace=workspace, user=user),
        WorkspaceMember(workspace=other_workspace, user=user),
        Asset(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, source_type="text", title="行业证据笔记"),
        Asset(tenant_id=tenant.id, workspace_id=other_workspace.id, created_by=user.id, source_type="text", title="行业证据秘密"),
        KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="行业知识卡片", definition="用户需要可追溯证据"),
        ContentDraft(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="行业内容草稿", body="证据驱动的内容"),
    ])
    await workbench_session.flush()

    result = await WorkbenchService(workbench_session).search(
        query="行业", workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id,
    )

    assert result["total"] == 3
    assert {item["kind"] for item in result["items"]} == {"asset", "knowledge", "content_draft"}
    assert all("秘密" not in item["title"] for item in result["items"])


@pytest.mark.asyncio
async def test_workbench_search_sorts_mixed_timezone_datetimes(workbench_session, monkeypatch):
    tenant = Tenant(name="Timezone tenant", contact_email=f"{uuid4()}@example.com")
    user = User(tenant=tenant, username=f"timezone-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
    workspace = Workspace(tenant=tenant, name="Timezone workspace")
    workbench_session.add_all([tenant, user, workspace])
    await workbench_session.flush()
    workbench_session.add(WorkspaceMember(workspace=workspace, user=user))
    workbench_session.add_all([
        Asset(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, source_type="text", title="排序验收素材"),
        KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="排序验收知识", definition="时区归一化"),
    ])
    await workbench_session.flush()

    original_item = WorkbenchService._item

    def mixed_timezone_item(resource_id, kind, title, snippet, route, created_at, metadata=None):
        if kind == "asset":
            created_at = datetime(2026, 10, 12, 11, tzinfo=timezone.utc)
        elif kind == "knowledge":
            created_at = datetime(2026, 10, 12, 10)
        return original_item(resource_id, kind, title, snippet, route, created_at, metadata)

    monkeypatch.setattr(WorkbenchService, "_item", staticmethod(mixed_timezone_item))

    result = await WorkbenchService(workbench_session).search(
        query="排序验收", workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id,
    )

    assert [item["kind"] for item in result["items"]] == ["asset", "knowledge"]


@pytest.mark.asyncio
async def test_workbench_task_center_aggregates_pending_domain_work(workbench_session):
    tenant = Tenant(name="Task tenant", contact_email=f"{uuid4()}@example.com")
    user = User(tenant=tenant, username=f"task-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
    workspace = Workspace(tenant=tenant, name="Task workspace")
    workbench_session.add_all([tenant, user, workspace])
    await workbench_session.flush()
    workbench_session.add(WorkspaceMember(workspace=workspace, user=user))
    draft = ContentDraft(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="已审核草稿", body="正文", review_status="approved")
    workbench_session.add_all([
        Asset(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, source_type="text", title="待处理素材"),
        KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="待审核知识", definition="需要证据"),
        ContentDraft(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="待审核草稿", body="正文"), draft,
    ])
    await workbench_session.flush()
    workbench_session.add(ContentPublishRecord(tenant_id=tenant.id, workspace_id=workspace.id, draft_id=draft.id, platform="manual", status="ready"))
    await workbench_session.flush()

    result = await WorkbenchService(workbench_session).list_tasks(
        workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id,
    )

    assert result["total"] == 4
    assert {item["kind"] for item in result["items"]} == {"asset", "knowledge_review", "content_review", "content_publish"}
    assert all(item["priority"] >= 1 for item in result["items"])
    routes_by_kind = {item["kind"]: item["route"] for item in result["items"]}
    assert routes_by_kind["asset"].startswith("/assets?asset_id=")
    assert routes_by_kind["knowledge_review"].startswith("/knowledge?item_id=")
    assert routes_by_kind["content_review"].startswith("/content?draft_id=")
    assert routes_by_kind["content_publish"].startswith("/content?publish_id=")
