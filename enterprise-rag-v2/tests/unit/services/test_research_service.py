from uuid import UUID, uuid4

import pytest
from unittest.mock import AsyncMock
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import AgentApproval, AgentOutput, AgentRun, Asset, Base, Dataset, KnowledgeEvidence, ResearchEvidence, ResearchFinding, ResearchProject, ResearchReport, ResearchRun, ResearchSource, Tenant, User, Workspace, WorkspaceMember
from infrastructure.queue import research_tasks
from services.impl.agent_runtime_service import AgentRuntimeService
from services.impl.research_service import ResearchService


@pytest.fixture
async def research_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _identity(session: AsyncSession):
    tenant = Tenant(name="Research tenant", contact_email=f"{uuid4()}@example.com")
    user = User(tenant=tenant, username=f"research-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
    workspace = Workspace(tenant=tenant, name="Research workspace")
    session.add_all([tenant, user, workspace])
    await session.flush()
    session.add(WorkspaceMember(workspace=workspace, user=user, role="member"))
    await session.flush()
    return tenant, user, workspace


@pytest.mark.asyncio
async def test_research_project_and_run_are_workspace_scoped(research_session):
    tenant, user, workspace = await _identity(research_session)
    service = ResearchService(research_session)
    async def allow_test_url(_url: str) -> None:
        return None
    service.fetcher._validate_url = allow_test_url
    project = await service.create_project(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={
            "workspace_id": workspace.id,
            "name": "行业趋势",
            "description": "验证研究对象关系",
            "questions": [{"question": "市场有哪些变化？", "sort_order": 0}],
            "samples": [{"source_uri": "https://example.com/report"}],
            "metadata": {},
        },
    )
    assert project["sample_count"] == 1
    run = await service.create_run(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, limits={"max_source_bytes": 1024},
    )
    assert run["status"] == "pending"
    assert run["agent_run_id"] is not None
    agent_run = await AgentRuntimeService(research_session).get_run(
        agent_run_id=UUID(str(run["agent_run_id"])), tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert len(agent_run["steps"]) == 5
    assert agent_run["steps"][0]["step_key"] == "collect_sources"
    runtime = AgentRuntimeService(research_session)
    await runtime.mark_step(agent_run_id=UUID(str(run["agent_run_id"])), step_key="collect_sources", status="completed", output={"source_count": 1})
    await runtime.request_approval(agent_run_id=UUID(str(run["agent_run_id"])), step_key="human_review")
    assert (await research_session.scalar(select(AgentOutput.id))) is not None
    assert (await research_session.scalar(select(AgentApproval.id))) is not None
    cancelled = await runtime.cancel_run(
        agent_run_id=UUID(str(run["agent_run_id"])), tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert cancelled["status"] == "cancelled"
    retried = await runtime.retry_run(
        agent_run_id=UUID(str(run["agent_run_id"])), tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert retried["status"] == "queued"
    assert retried["retry_count"] == 1
    runs = await service.list_runs(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        page=1, page_size=20, is_superuser=False,
    )
    assert runs["total"] == 1

    events = await runtime.list_events(
        agent_run_id=UUID(str(run["agent_run_id"])), tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert any(event["event_type"] == "output" for event in events)


@pytest.mark.asyncio
async def test_research_run_reserves_tenant_quota_by_requested_budget(research_session):
    tenant, user, workspace = await _identity(research_session)
    quota = type("Quota", (), {"check_and_increment": AsyncMock(return_value=(True, 1, 10))})()
    service = ResearchService(research_session, quota_service=quota)
    project = await service.create_project(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "name": "配额研究", "questions": [{"question": "配额？"}]},
    )
    await service.create_run(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, limits={"max_sources": 7, "max_output_tokens": 900},
    )
    assert [call.args for call in quota.check_and_increment.await_args_list] == [
        (str(tenant.id), "research_runs_monthly", 1),
        (str(tenant.id), "research_sources_monthly", 7),
        (str(tenant.id), "research_output_tokens_monthly", 900),
    ]


@pytest.mark.asyncio
async def test_research_run_retry_reuses_agent_run_and_resets_state(research_session):
    tenant, user, workspace = await _identity(research_session)
    service = ResearchService(research_session)
    project = await service.create_project(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "name": "可重试研究", "questions": [{"question": "失败后怎么办？"}]},
    )
    run = await service.create_run(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, limits={},
    )
    research_run = await research_session.get(ResearchRun, str(run["id"]))
    research_run.status = "failed"
    research_run.current_stage = "failed"
    agent_run = await research_session.get(AgentRun, str(run["agent_run_id"]))
    agent_run.status = "failed"
    await research_session.flush()
    retried = await service.retry_run(
        run_id=UUID(str(run["id"])), tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert retried["status"] == "pending"
    assert retried["agent_run_id"] == run["agent_run_id"]
    assert research_run.retry_count == 1


@pytest.mark.asyncio
async def test_research_cancel_syncs_agent_and_can_be_retried(research_session):
    tenant, user, workspace = await _identity(research_session)
    service = ResearchService(research_session)
    project = await service.create_project(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "name": "取消后重试研究", "questions": [{"question": "取消后能否恢复？"}]},
    )
    run = await service.create_run(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, limits={},
    )

    cancelled = await service.cancel_run(
        run_id=UUID(str(run["id"])), tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert cancelled["status"] == "cancelled"
    assert cancelled["current_stage"] == "cancelled"
    agent_run = await research_session.get(AgentRun, str(run["agent_run_id"]))
    assert agent_run.status == "cancelled"
    assert agent_run.current_step == "cancelled"

    retried = await service.retry_run(
        run_id=UUID(str(run["id"])), tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert retried["status"] == "pending"
    assert retried["current_stage"] is None
    assert retried["progress"] == 0
    assert agent_run.status == "queued"


@pytest.mark.asyncio
async def test_research_quota_reservation_rolls_back_on_partial_failure(research_session):
    tenant, user, workspace = await _identity(research_session)
    quota = type("Quota", (), {
        "check_and_increment": AsyncMock(side_effect=[(True, 1, 10), RuntimeError("quota")]),
        "decrement_usage": AsyncMock(return_value=0),
    })()
    service = ResearchService(research_session, quota_service=quota)
    project = await service.create_project(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "name": "配额回滚", "questions": [{"question": "配额？"}]},
    )
    with pytest.raises(RuntimeError, match="quota"):
        await service.create_run(
            project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
            is_superuser=False, limits={"max_sources": 7, "max_output_tokens": 900},
        )
    quota.decrement_usage.assert_awaited_once_with(str(tenant.id), "research_runs_monthly", 1)


@pytest.mark.asyncio
async def test_research_evidence_and_findings_are_queryable_with_workspace_scope(research_session):
    tenant, user, workspace = await _identity(research_session)
    service = ResearchService(research_session)
    project = await service.create_project(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "name": "证据工作区", "questions": [{"question": "证据？"}]},
    )
    run = await service.create_run(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, limits={},
    )
    source = ResearchSource(
        tenant_id=tenant.id, workspace_id=workspace.id, run_id=run["id"],
        title="来源 A", source_uri="https://example.com/a", status="available",
    )
    research_session.add(source)
    await research_session.flush()
    evidence = ResearchEvidence(
        tenant_id=tenant.id, workspace_id=workspace.id, run_id=run["id"], source_id=source.id,
        quote="可追溯原文", locator="p.1",
    )
    research_session.add(evidence)
    await research_session.flush()
    research_session.add(ResearchFinding(
        tenant_id=tenant.id, workspace_id=workspace.id, run_id=run["id"],
        claim="证据支持结论", evidence_ids=[str(evidence.id)],
    ))
    await research_session.flush()

    listed_evidence = await service.list_evidence(
        run_id=UUID(str(run["id"])), tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    listed_findings = await service.list_findings(
        run_id=UUID(str(run["id"])), tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert listed_evidence[0]["source_title"] == "来源 A"
    assert listed_findings[0]["evidence_ids"] == [str(evidence.id)]


@pytest.mark.asyncio
async def test_research_rejects_private_source_url(research_session):
    tenant, user, workspace = await _identity(research_session)
    with pytest.raises(ValueError):
        await ResearchService(research_session).create_project(
            tenant_id=tenant.id, user_id=user.id, is_superuser=False,
            data={"workspace_id": workspace.id, "name": "不安全研究", "samples": [{"source_uri": "http://127.0.0.1/admin"}]},
        )


@pytest.mark.asyncio
async def test_research_run_validates_and_persists_budget(research_session):
    tenant, user, workspace = await _identity(research_session)
    service = ResearchService(research_session)
    project = await service.create_project(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "name": "预算研究", "questions": [{"question": "结论？"}]},
    )
    with pytest.raises(ValueError):
        await service.create_run(project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id, is_superuser=False, limits={"max_sources": 0})
    run = await service.create_run(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, limits={"max_sources": 3, "max_output_tokens": 512},
    )
    stored = await research_session.get(ResearchRun, run["id"])
    assert stored.limits["max_sources"] == 3
    assert stored.plan["budget"]["max_output_tokens"] == 512

    default_run = await service.create_run(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, limits={},
    )
    default_stored = await research_session.get(ResearchRun, default_run["id"])
    assert default_stored.limits["max_sources"] == 10


@pytest.mark.asyncio
async def test_research_model_synthesis_is_opt_in(monkeypatch):
    monkeypatch.delenv("RESEARCH_ENABLE_LLM", raising=False)
    monkeypatch.setattr(research_tasks, "is_effective_openai_api_key", lambda _key: False)
    result = await research_tasks._synthesize_with_configured_model(None, None, [])
    assert result == (None, None, [])


@pytest.mark.asyncio
async def test_research_worker_checkpoint_stops_cancelled_run():
    run = ResearchRun(id=uuid4(), tenant_id=uuid4())
    session = type("CheckpointSession", (), {
        "scalar": AsyncMock(return_value="cancelled"),
        "rollback": AsyncMock(),
    })()

    assert await research_tasks._cancelled_since_last_checkpoint(session, run) is True
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_research_worker_checkpoint_keeps_active_run():
    run = ResearchRun(id=uuid4(), tenant_id=uuid4())
    session = type("CheckpointSession", (), {
        "scalar": AsyncMock(return_value="searching"),
        "rollback": AsyncMock(),
    })()

    assert await research_tasks._cancelled_since_last_checkpoint(session, run) is False
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_external_search_failure_is_recorded_as_internal_fallback(research_session, monkeypatch):
    tenant, user, workspace = await _identity(research_session)
    project = ResearchProject(
        tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, name="外部降级研究",
        extra_metadata={"external_search": {"enabled": True, "queries": ["行业趋势"]}},
    )
    research_session.add(project)
    await research_session.flush()
    run = ResearchRun(tenant_id=tenant.id, workspace_id=workspace.id, project_id=project.id, created_by=user.id, plan={}, limits={})
    research_session.add(run)
    await research_session.flush()

    class FailingProvider:
        def __init__(self, **_kwargs):
            pass

        async def search(self, _query):
            raise research_tasks.ExternalSearchUnavailable("service unavailable")

    monkeypatch.setattr(research_tasks, "ExternalSearchProvider", FailingProvider)
    assert await research_tasks._collect_external_sources(research_session, run) == []
    assert run.plan["source_collection"] == {"enabled": True, "queries": 1, "attempted": 1, "failed": 1, "source_count": 0, "fallback": "internal"}


@pytest.mark.asyncio
async def test_research_report_review_is_workspace_scoped(research_session):
    tenant, user, workspace = await _identity(research_session)
    service = ResearchService(research_session)
    project = await service.create_project(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "name": "待审核研究", "questions": [{"question": "结论？"}]},
    )
    run = await service.create_run(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, limits={},
    )
    report = ResearchReport(
        tenant_id=tenant.id, workspace_id=workspace.id, run_id=run["id"],
        content_markdown="# 研究报告\n\n有来源的内容", content_json={"evidence_only": True},
    )
    research_session.add(report)
    await research_session.flush()
    reviewed = await service.review_report(
        report_id=report.id, tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, review_status="approved",
    )
    assert reviewed["review_status"] == "approved"


@pytest.mark.asyncio
async def test_agent_definition_rejects_unregistered_agent_type(research_session):
    tenant, user, workspace = await _identity(research_session)
    with pytest.raises(ValueError):
        await AgentRuntimeService(research_session).create_definition(
            tenant_id=tenant.id, user_id=user.id, is_superuser=False,
            data={"workspace_id": workspace.id, "name": "任意工具 Agent", "agent_type": "arbitrary_tool"},
        )


@pytest.mark.asyncio
async def test_agent_definition_supports_asset_organize_workflow(research_session):
    tenant, user, workspace = await _identity(research_session)
    definition = await AgentRuntimeService(research_session).create_definition(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "name": "素材整理", "agent_type": "asset_organize"},
    )
    assert definition["agent_type"] == "asset_organize"
    assert definition["workflow"][0]["key"] == "read_material"


@pytest.mark.asyncio
async def test_agent_approval_workbench_lists_and_reviews_pending_approval(research_session):
    tenant, user, workspace = await _identity(research_session)
    service = ResearchService(research_session)
    project = await service.create_project(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "name": "审批工作台研究", "questions": [{"question": "结论？"}]},
    )
    run = await service.create_run(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, limits={},
    )
    runtime = AgentRuntimeService(research_session)
    await runtime.request_approval(agent_run_id=UUID(str(run["agent_run_id"])), step_key="human_review")
    approvals = await runtime.list_approvals(
        workspace_id=workspace.id, tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert len(approvals) == 1
    reviewed = await runtime.review_approval(
        approval_id=UUID(str(approvals[0]["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, status="approved", comment="证据链完整",
    )
    assert reviewed["status"] == "approved"
    with pytest.raises(ValueError):
        await runtime.review_approval(
            approval_id=UUID(str(approvals[0]["id"])), tenant_id=tenant.id, user_id=user.id,
            is_superuser=False, status="rejected",
        )


@pytest.mark.asyncio
async def test_approved_report_can_be_published_to_workspace_dataset(research_session):
    tenant, user, workspace = await _identity(research_session)
    dataset = Dataset(workspace_id=workspace.id, name="研究发布库", embedding_model="test-model")
    research_session.add(dataset)
    await research_session.flush()
    service = ResearchService(research_session)
    project = await service.create_project(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "name": "可发布研究", "questions": [{"question": "结论？"}]},
    )
    run = await service.create_run(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, limits={},
    )
    report = ResearchReport(
        tenant_id=tenant.id, workspace_id=workspace.id, run_id=run["id"],
        content_markdown="# 已审核研究报告", review_status="approved",
    )
    research_session.add(report)
    await research_session.flush()
    published = await service.publish_report(
        report_id=report.id, dataset_id=dataset.id, tenant_id=tenant.id,
        user_id=user.id, is_superuser=False,
    )
    assert published["published_dataset_id"] == dataset.id
    assert published["published_document_id"] is not None
    asset = (await research_session.execute(select(Asset).where(Asset.dataset_id == dataset.id))).scalar_one()
    assert str(asset.legacy_document_id) == str(published["published_document_id"])


@pytest.mark.asyncio
async def test_research_report_can_be_edited_and_returns_to_review(research_session):
    tenant, user, workspace = await _identity(research_session)
    service = ResearchService(research_session)
    project = await service.create_project(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "name": "可编辑研究", "questions": [{"question": "结论？"}]},
    )
    run = await service.create_run(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, limits={},
    )
    report = ResearchReport(
        tenant_id=tenant.id, workspace_id=workspace.id, run_id=run["id"],
        content_markdown="# 初始报告", review_status="approved",
    )
    research_session.add(report)
    await research_session.flush()
    updated = await service.update_report(
        report_id=report.id, tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, content_markdown="# 修订报告",
    )
    assert updated["content_markdown"] == "# 修订报告"
    assert updated["version"] == 2
    assert updated["review_status"] == "draft"


@pytest.mark.asyncio
async def test_approved_report_can_be_promoted_to_knowledge_card(research_session):
    tenant, user, workspace = await _identity(research_session)
    service = ResearchService(research_session)
    project = await service.create_project(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "name": "知识沉淀研究", "questions": [{"question": "结论？"}]},
    )
    run = await service.create_run(
        project_id=UUID(str(project["id"])), tenant_id=tenant.id, user_id=user.id,
        is_superuser=False, limits={},
    )
    source = ResearchSource(tenant_id=tenant.id, workspace_id=workspace.id, run_id=run["id"], source_uri="https://example.com/source", title="来源")
    research_session.add(source)
    await research_session.flush()
    evidence = ResearchEvidence(tenant_id=tenant.id, workspace_id=workspace.id, run_id=run["id"], source_id=source.id, quote="可追溯摘录", locator="p1")
    report = ResearchReport(tenant_id=tenant.id, workspace_id=workspace.id, run_id=run["id"], content_markdown="# 研究报告", review_status="approved")
    research_session.add_all([evidence, report])
    await research_session.flush()
    published = await service.publish_report_to_knowledge(
        report_id=report.id, tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert published["published_knowledge_item_id"] is not None
    linked = (await research_session.execute(select(KnowledgeEvidence).where(KnowledgeEvidence.research_evidence_id == evidence.id))).scalar_one()
    assert str(linked.knowledge_item_id) == str(published["published_knowledge_item_id"])
