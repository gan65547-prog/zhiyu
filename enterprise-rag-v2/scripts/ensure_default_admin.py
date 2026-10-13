"""Ensure the default tenant, administrator, and workspace exist.

This intentionally does not call ``Base.metadata.create_all``. Production
databases are managed by migrations and may contain legacy tables whose model
types are not compatible with a full metadata create pass.
"""

import asyncio
import os
import sys
from datetime import datetime
from uuid import uuid4

import bcrypt
from sqlalchemy import insert, select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.database.models import Tenant, User, Workspace, WorkspaceMember
from infrastructure.database.session import engine


DEFAULT_EMAIL = os.environ.get("DEFAULT_ADMIN_EMAIL", "")
DEFAULT_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "")


async def ensure_default_admin() -> None:
    if not DEFAULT_EMAIL or not DEFAULT_PASSWORD:
        raise RuntimeError("Set DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_PASSWORD before bootstrapping.")

    async with engine.begin() as conn:
        result = await conn.execute(select(Tenant).where(Tenant.contact_email == DEFAULT_EMAIL))
        tenant = result.scalar_one_or_none()
        if tenant is None:
            tenant_id = str(uuid4())
            await conn.execute(
                insert(Tenant).values(
                    id=tenant_id,
                    name="Default Tenant",
                    contact_email=DEFAULT_EMAIL,
                    plan="enterprise",
                    status="active",
                    extra_metadata={"is_default": True},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
        else:
            tenant_id = tenant.id

        result = await conn.execute(select(User).where(User.email == DEFAULT_EMAIL))
        user = result.scalar_one_or_none()
        if user is None:
            user_id = str(uuid4())
            await conn.execute(
                insert(User).values(
                    id=user_id,
                    tenant_id=tenant_id,
                    username="admin",
                    email=DEFAULT_EMAIL,
                    hashed_password=bcrypt.hashpw(
                        DEFAULT_PASSWORD.encode("utf-8"), bcrypt.gensalt()
                    ).decode("utf-8"),
                    is_active=True,
                    is_superuser=True,
                    extra_metadata={"is_default": True},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
        else:
            user_id = user.id

        result = await conn.execute(
            select(Workspace).where(
                Workspace.tenant_id == tenant_id,
                Workspace.name == "默认工作空间",
            )
        )
        workspace = result.scalar_one_or_none()
        if workspace is None:
            workspace_id = str(uuid4())
            await conn.execute(
                insert(Workspace).values(
                    id=workspace_id,
                    tenant_id=tenant_id,
                    name="默认工作空间",
                    description="系统默认创建的工作空间",
                    is_default=True,
                    extra_metadata={"is_default": True},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
        else:
            workspace_id = workspace.id

        result = await conn.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        if result.scalar_one_or_none() is None:
            await conn.execute(
                insert(WorkspaceMember).values(
                    id=str(uuid4()),
                    workspace_id=workspace_id,
                    user_id=user_id,
                    role="owner",
                    joined_at=datetime.utcnow(),
                )
            )

    print(f"Default admin ready: {DEFAULT_EMAIL}")


if __name__ == "__main__":
    asyncio.run(ensure_default_admin())
