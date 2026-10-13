import asyncio
from uuid import uuid4
from datetime import datetime
from sqlalchemy import select, insert
from infrastructure.database.session import engine
from infrastructure.database.models import Tenant, User, Workspace, WorkspaceMember

async def add_workspace():
    async with engine.begin() as conn:
        result = await conn.execute(select(Tenant).where(Tenant.contact_email == 'admin@default.com'))
        tenant = result.scalar_one_or_none()
        if not tenant:
            print('Tenant not found')
            return
        tenant_id = tenant.id if hasattr(tenant, 'id') and not isinstance(tenant.id, str) else tenant

        result = await conn.execute(select(User).where(User.email == 'admin@default.com'))
        user = result.scalar_one_or_none()
        if not user:
            print('User not found')
            return
        user_id = user.id if hasattr(user, 'id') and not isinstance(user.id, str) else user

        result = await conn.execute(
            select(Workspace).where(Workspace.tenant_id == tenant_id, Workspace.name == '默认工作空间')
        )
        ws = result.scalar_one_or_none()
        if ws:
            print('Workspace exists')
            return

        ws_id = str(uuid4())
        await conn.execute(insert(Workspace).values(
            id=ws_id,
            tenant_id=tenant_id,
            name='默认工作空间',
            description='System default workspace',
            is_default=True,
            extra_metadata={'is_default': True},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        ))
        print(f'Created workspace: {ws_id}')

        await conn.execute(insert(WorkspaceMember).values(
            id=str(uuid4()),
            workspace_id=ws_id,
            user_id=user_id,
            role='owner',
            joined_at=datetime.utcnow()
        ))
        print('Added member to workspace')

asyncio.run(add_workspace())
print('Done!')