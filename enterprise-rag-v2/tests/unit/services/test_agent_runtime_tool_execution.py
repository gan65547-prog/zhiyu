from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models import AgentDefinition, Base, Tenant, User, Workspace, WorkspaceMember
from services.impl.agent_runtime_service import AgentRuntimeService


@pytest_asyncio.fixture
async def runtime_context():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        tenant = Tenant(name="Runtime tenant", contact_email=f"{uuid4()}@example.com")
        user = User(tenant=tenant, username=f"runtime-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
        workspace = Workspace(tenant=tenant, name="Runtime workspace")
        session.add_all([tenant, user, workspace])
        await session.flush()
        session.add(WorkspaceMember(workspace=workspace, user=user))
        await session.flush()
        yield session, tenant, user, workspace
    await engine.dispose()


@pytest.mark.asyncio
async def test_registered_tool_runs_and_writes_auditable_step_output(runtime_context):
    session, tenant, user, workspace = runtime_context
    definition = AgentDefinition(
        tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id,
        name="术语工具", agent_type="asset_organize", workflow=[{"key": "terms", "tool": "extract_terms", "input": {}}],
    )
    session.add(definition)
    await session.flush()
    runtime = AgentRuntimeService(session)
    run = await runtime.create_run(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "definition_id": definition.id},
    )
    result = await runtime.execute_tool_step(
        agent_run_id=run["id"], step_key="terms", arguments={"text": "AI 工作台 platform"},
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert result["status"] == "completed"
    assert result["output"]["terms"] == ["AI", "工作台", "platform"]
    refreshed = await runtime.get_run(agent_run_id=run["id"], tenant_id=tenant.id, user_id=user.id, is_superuser=False)
    assert refreshed["status"] == "completed"
    assert refreshed["steps"][0]["output_json"]["tool"] == "extract_terms"


@pytest.mark.asyncio
async def test_approval_required_tool_stops_before_execution(runtime_context):
    session, tenant, user, workspace = runtime_context
    definition = AgentDefinition(
        tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id,
        name="网页工具", agent_type="asset_organize", workflow=[{"key": "fetch", "tool": "safe_fetch_url", "input": {}}],
    )
    session.add(definition)
    await session.flush()
    runtime = AgentRuntimeService(session)
    run = await runtime.create_run(tenant_id=tenant.id, user_id=user.id, is_superuser=False, data={"workspace_id": workspace.id, "definition_id": definition.id})
    result = await runtime.execute_tool_step(
        agent_run_id=run["id"], step_key="fetch", arguments={"url": "https://example.com"},
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert result["status"] == "waiting_approval"
    assert result["approval_id"] is not None
    assert (await runtime.get_run(agent_run_id=run["id"], tenant_id=tenant.id, user_id=user.id, is_superuser=False))["status"] == "waiting_approval"


@pytest.mark.asyncio
async def test_failed_tool_run_is_persisted_and_can_be_retried(runtime_context):
    session, tenant, user, workspace = runtime_context
    definition = AgentDefinition(
        tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id,
        name="失败工具", agent_type="asset_organize", workflow=[{"key": "terms", "tool": "extract_terms", "input": {}}],
    )
    session.add(definition)
    await session.flush()
    runtime = AgentRuntimeService(session)
    run = await runtime.create_run(
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
        data={"workspace_id": workspace.id, "definition_id": definition.id},
    )

    result = await runtime.execute_tool_step(
        agent_run_id=run["id"], step_key="terms", arguments={},
        tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert result["status"] == "failed"
    assert "缺少 text" in result["output"]["error"]
    failed = await runtime.get_run(agent_run_id=run["id"], tenant_id=tenant.id, user_id=user.id, is_superuser=False)
    assert failed["status"] == "failed"
    assert failed["steps"][0]["status"] == "failed"

    retried = await runtime.retry_run(
        agent_run_id=run["id"], tenant_id=tenant.id, user_id=user.id, is_superuser=False,
    )
    assert retried["status"] == "queued"
    assert retried["retry_count"] == 1
    assert retried["steps"][0]["status"] == "pending"
