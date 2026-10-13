from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import (
    AgentDefinition,
    AgentRun,
    Asset,
    Base,
    ContentDraft,
    ContentMetric,
    ContentPublishRecord,
    KnowledgeEvidence,
    KnowledgeItem,
    ResearchProject,
    ResearchReport,
    ResearchRun,
    Tenant,
    User,
    Workspace,
    WorkspaceMember,
)
from services.impl.data_center_service import DataCenterService


@pytest_asyncio.fixture
async def data_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_data_center_overview_is_workspace_scoped_and_explainable(data_session):
    tenant = Tenant(name="Data tenant", contact_email=f"{uuid4()}@example.com")
    user = User(tenant=tenant, username=f"data-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
    workspace = Workspace(tenant=tenant, name="Data workspace")
    data_session.add_all([tenant, user, workspace])
    await data_session.flush()
    data_session.add(WorkspaceMember(workspace=workspace, user=user))
    asset = Asset(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, source_type="text", title="素材", status="completed")
    knowledge = KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="知识", definition="定义", review_status="approved")
    project = ResearchProject(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, name="研究")
    definition = AgentDefinition(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, name="Agent", agent_type="asset_organize", workflow=[])
    draft = ContentDraft(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="内容", body="正文")
    data_session.add_all([asset, knowledge, project, definition, draft])
    await data_session.flush()
    data_session.add(KnowledgeEvidence(tenant_id=tenant.id, workspace_id=workspace.id, knowledge_item_id=knowledge.id, quote="证据", created_by=user.id))
    completed_run = ResearchRun(tenant_id=tenant.id, workspace_id=workspace.id, project_id=project.id, created_by=user.id, status="completed")
    data_session.add(completed_run)
    await data_session.flush()
    data_session.add_all([
        ResearchReport(tenant_id=tenant.id, workspace_id=workspace.id, run_id=completed_run.id, content_markdown="# 报告"),
        AgentRun(tenant_id=tenant.id, workspace_id=workspace.id, definition_id=definition.id, created_by=user.id, status="completed"),
    ])
    publish = ContentPublishRecord(tenant_id=tenant.id, workspace_id=workspace.id, draft_id=draft.id, platform="manual")
    data_session.add(publish)
    await data_session.flush()
    data_session.add(ContentMetric(tenant_id=tenant.id, workspace_id=workspace.id, publish_record_id=publish.id, impressions=100, clicks=10, likes=5))
    await data_session.flush()

    overview = await DataCenterService(data_session).overview(
        workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id,
    )

    assert overview["assets"]["by_status"] == {"completed": 1}
    assert overview["health"]["knowledge_evidence_coverage"] == 1.0
    assert overview["health"]["research_success_rate"] == 1.0
    assert overview["content_performance"]["click_through_rate"] == 0.1


@pytest.mark.asyncio
async def test_data_center_rejects_non_member(data_session):
    tenant = Tenant(name="Private tenant", contact_email=f"{uuid4()}@example.com")
    owner = User(tenant=tenant, username=f"owner-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
    outsider = User(tenant=tenant, username=f"outsider-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
    workspace = Workspace(tenant=tenant, name="Private workspace")
    data_session.add_all([tenant, owner, outsider, workspace])
    await data_session.flush()
    data_session.add(WorkspaceMember(workspace=workspace, user=owner))
    await data_session.flush()

    with pytest.raises(PermissionError):
        await DataCenterService(data_session).overview(
            workspace_id=workspace.id, tenant_id=tenant.id, user_id=outsider.id,
        )
