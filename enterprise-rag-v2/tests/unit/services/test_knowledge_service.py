from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import Base, KnowledgeItem, Tenant, User, Workspace, WorkspaceMember
from services.impl.knowledge_service import KnowledgeService


@pytest.fixture
async def knowledge_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _identity(session: AsyncSession):
    tenant = Tenant(name="Knowledge tenant", contact_email=f"{uuid4()}@example.com")
    user = User(
        tenant=tenant, username=f"knowledge-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash"
    )
    workspace = Workspace(tenant=tenant, name="Knowledge workspace")
    session.add_all([tenant, user, workspace])
    await session.flush()
    session.add(WorkspaceMember(workspace=workspace, user=user, role="member"))
    await session.flush()
    return tenant, user, workspace


@pytest.mark.asyncio
async def test_knowledge_item_requires_evidence_for_approval(knowledge_session):
    tenant, user, workspace = await _identity(knowledge_session)
    service = KnowledgeService(knowledge_session)
    item = await service.create_item(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        workspace_id=workspace.id, title="行业定义", item_type="concept",
        definition="可审核的定义", metadata={"source": "manual"},
    )
    with pytest.raises(ValueError, match="证据"):
        await service.review_item(
            item_id=UUID(str(item["id"])), tenant_id=tenant.id, user_id=user.id,
            is_superuser=False, review_status="approved",
        )


@pytest.mark.asyncio
async def test_knowledge_item_workspace_isolation(knowledge_session):
    tenant, user, workspace = await _identity(knowledge_session)
    other_tenant = Tenant(name="Other", contact_email=f"{uuid4()}@example.com")
    other_user = User(
        tenant=other_tenant, username=f"other-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash"
    )
    other_workspace = Workspace(tenant=other_tenant, name="Other workspace")
    knowledge_session.add_all([other_tenant, other_user, other_workspace])
    await knowledge_session.flush()
    service = KnowledgeService(knowledge_session)
    item = await service.create_item(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        workspace_id=workspace.id, title="隔离测试", item_type="topic", definition="内部内容",
    )
    assert await service.get_item(
        item_id=UUID(str(item["id"])), tenant_id=other_tenant.id,
        user_id=other_user.id, is_superuser=False,
    ) is None
    assert await knowledge_session.get(KnowledgeItem, UUID(str(item["id"]))) is not None


@pytest.mark.asyncio
async def test_knowledge_item_update_and_rollback_create_immutable_versions(knowledge_session):
    tenant, user, workspace = await _identity(knowledge_session)
    service = KnowledgeService(knowledge_session)
    item = await service.create_item(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        workspace_id=workspace.id, title="初始标题", item_type="topic", definition="初始定义",
    )
    item_id = UUID(str(item["id"]))
    await service.update_item(
        item_id=item_id, tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        changes={"title": "新标题", "definition": "新定义"},
    )
    assert (await service.get_item(item_id=item_id, tenant_id=tenant.id, user_id=user.id, is_superuser=False))["review_status"] == "draft"
    versions = await service.list_versions(
        item_id=item_id, tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert [version["version"] for version in versions] == [2, 1]
    restored = await service.rollback_item(
        item_id=item_id, version_id=UUID(str(versions[-1]["id"])), tenant_id=tenant.id,
        user_id=user.id, is_superuser=False,
    )
    assert restored["title"] == "初始标题"
    assert restored["definition"] == "初始定义"
    assert len(await service.list_versions(item_id=item_id, tenant_id=tenant.id, user_id=user.id, is_superuser=False)) == 3
