import asyncio
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from infrastructure.database.models import Asset, Base, Tenant, User, Workspace, WorkspaceMember
from services.impl.workbench_service import WorkbenchService


@pytest_asyncio.fixture
async def tenant_factory(tmp_path):
    # aiosqlite defaults to NullPool, which rejects pool_size.  Use the async
    # queue pool explicitly so this test still exercises concurrent sessions
    # across supported SQLAlchemy/SQLite combinations.
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'workbench.db'}",
        poolclass=AsyncAdaptedQueuePool,
        pool_size=10,
        max_overflow=0,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        identities = []
        for index in ("a", "b"):
            tenant = Tenant(name=f"Tenant {index}", contact_email=f"{uuid4()}@example.com")
            user = User(tenant=tenant, username=f"user-{index}-{uuid4()}", email=f"{uuid4()}@example.com", hashed_password="hash")
            workspace = Workspace(tenant=tenant, name=f"Workspace {index}")
            session.add_all([tenant, user, workspace])
            await session.flush()
            session.add(WorkspaceMember(workspace=workspace, user=user))
            session.add(Asset(tenant_id=tenant.id, workspace_id=workspace.id, created_by=user.id, source_type="text", title=f"secret-{index}"))
            identities.append((tenant.id, user.id, workspace.id, index))
        await session.commit()
    yield factory, identities
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_workbench_queries_keep_tenant_boundaries(tenant_factory):
    factory, identities = tenant_factory

    async def query(identity):
        tenant_id, user_id, workspace_id, marker = identity
        async with factory() as session:
            result = await WorkbenchService(session).search(
                query="secret", workspace_id=workspace_id, tenant_id=tenant_id, user_id=user_id,
            )
            return marker, result

    results = await asyncio.gather(*(query(identity) for identity in identities for _ in range(10)))
    for marker, result in results:
        assert result["total"] == 1
        assert result["items"][0]["title"] == f"secret-{marker}"
