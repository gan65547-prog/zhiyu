import json
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import Base, KnowledgeItem, KnowledgeRelation, Tenant, User, Workspace, WorkspaceMember
from services.impl.knowledge_relation_service import KnowledgeRelationService
import services.impl.knowledge_relation_service as relation_module


@pytest_asyncio.fixture
async def relation_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _identity(session):
    tenant = Tenant(name="Graph tenant", contact_email=f"{uuid4()}@example.com")
    user = User(tenant=tenant, username=f"graph-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
    workspace = Workspace(tenant=tenant, name="Graph workspace")
    session.add_all([tenant, user, workspace])
    await session.flush()
    session.add(WorkspaceMember(workspace=workspace, user=user))
    await session.flush()
    return tenant, user, workspace


@pytest.mark.asyncio
async def test_relation_network_only_exposes_approved_nodes_and_is_idempotent(relation_session):
    tenant, user, workspace = await _identity(relation_session)
    source = KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="采购", definition="采购流程", review_status="approved")
    target = KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="决策", definition="决策因素", review_status="approved")
    draft = KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="草稿", definition="未审核", review_status="draft")
    relation_session.add_all([source, target, draft])
    await relation_session.flush()
    service = KnowledgeRelationService(relation_session)

    relation = await service.create(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False, workspace_id=workspace.id,
        source_item_id=source.id, target_item_id=target.id, relation_type="supports", description="采购影响决策",
    )
    duplicate = await service.create(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False, workspace_id=workspace.id,
        source_item_id=source.id, target_item_id=target.id, relation_type="supports",
    )
    assert relation["id"] == duplicate["id"]
    network = await service.network(tenant_id=tenant.id, user_id=user.id, is_superuser=False, workspace_id=workspace.id)
    assert {node["title"] for node in network["nodes"]} == {"采购", "决策"}
    assert len(network["edges"]) == 1

    with pytest.raises(ValueError, match="审核通过"):
        await service.create(
            tenant_id=tenant.id, user_id=user.id, is_superuser=False, workspace_id=workspace.id,
            source_item_id=source.id, target_item_id=draft.id, relation_type="supports",
        )


@pytest.mark.asyncio
async def test_relation_rejects_self_edge(relation_session):
    tenant, user, workspace = await _identity(relation_session)
    item = KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="节点", definition="定义", review_status="approved")
    relation_session.add(item)
    await relation_session.flush()

    with pytest.raises(ValueError, match="自身"):
        await KnowledgeRelationService(relation_session).create(
            tenant_id=tenant.id, user_id=user.id, is_superuser=False, workspace_id=workspace.id,
            source_item_id=item.id, target_item_id=item.id, relation_type="related",
        )


@pytest.mark.asyncio
async def test_relation_suggestions_are_review_only_and_skip_existing_edges(relation_session):
    tenant, user, workspace = await _identity(relation_session)
    source = KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="智能制造", definition="智能制造 数据闭环", review_status="approved")
    target = KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="数据治理", definition="数据治理 支撑智能制造", review_status="approved")
    relation_session.add_all([source, target])
    await relation_session.flush()
    suggestions = await KnowledgeRelationService(relation_session).suggestions(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False, workspace_id=workspace.id,
    )
    assert len(suggestions) == 1
    assert suggestions[0]["relation_type"] == "related"
    assert "智能制造" in suggestions[0]["matched_terms"]
    assert suggestions[0]["requires_human_review"] is True

    await KnowledgeRelationService(relation_session).create(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False, workspace_id=workspace.id,
        source_item_id=source.id, target_item_id=target.id, relation_type="related",
    )
    assert await KnowledgeRelationService(relation_session).suggestions(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False, workspace_id=workspace.id,
    ) == []


@pytest.mark.asyncio
async def test_model_relation_suggestions_are_validated_and_review_only(relation_session, monkeypatch):
    tenant, user, workspace = await _identity(relation_session)
    source = KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="供应链", definition="供应链风险", review_status="approved")
    target = KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="风险控制", definition="风险控制措施", review_status="approved")
    draft = KnowledgeItem(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, title="未审核卡片", definition="不应进入模型上下文", review_status="draft")
    relation_session.add_all([source, target, draft])
    await relation_session.flush()

    class FakeProvider:
        async def generate(self, _prompt, documents, **_kwargs):
            assert len(documents) == 2
            payload = [{"source_item_id": str(source.id), "target_item_id": str(target.id), "relation_type": "supports", "description": "风险控制支撑供应链", "score": 0.91}, {"source_item_id": str(draft.id), "target_item_id": str(target.id), "relation_type": "invalid", "score": 1}]
            return f"```json\n{json.dumps(payload, ensure_ascii=False)}\n```"

    monkeypatch.setattr(relation_module.LLMProviderFactory, "create", lambda _provider=None: FakeProvider())
    suggestions = await KnowledgeRelationService(relation_session).model_suggestions(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False, workspace_id=workspace.id,
    )
    assert len(suggestions) == 1
    assert suggestions[0]["relation_type"] == "supports"
    assert suggestions[0]["origin"] == "model"
    assert suggestions[0]["requires_human_review"] is True
    assert await relation_session.scalar(select(KnowledgeRelation.id)) is None
