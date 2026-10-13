"""
数据库初始化脚本

创建所有数据库表和初始数据
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from uuid import uuid4
from datetime import datetime
import bcrypt
from sqlalchemy import select, insert

from infrastructure.database.session import engine
from infrastructure.database.models import Base, Tenant, User, Workspace, WorkspaceMember


async def init_database():
    """初始化数据库"""
    print("开始初始化数据库...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("✅ 数据库表创建成功")

        result = await conn.execute(
            select(Tenant).where(Tenant.contact_email == "admin@default.com")
        )
        existing_tenant = result.scalar_one_or_none()

        if existing_tenant:
            print("✅ 默认租户已存在")
            tenant_id = existing_tenant.id
        else:
            tenant_id = str(uuid4())
            await conn.execute(
                insert(Tenant).values(
                    id=tenant_id,
                    name="Default Tenant",
                    contact_email="admin@default.com",
                    plan="enterprise",
                    status="active",
                    extra_metadata={"is_default": True},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 默认租户创建成功: {tenant_id}")

        result = await conn.execute(
            select(User).where(User.email == "admin@default.com")
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print("✅ 默认管理员已存在")
            admin_user_id = existing_user.id
        else:
            admin_user_id = str(uuid4())
            hashed_password = bcrypt.hashpw("Admin123!@#".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            await conn.execute(
                insert(User).values(
                    id=admin_user_id,
                    tenant_id=tenant_id,
                    username="admin",
                    email="admin@default.com",
                    hashed_password=hashed_password,
                    is_active=True,
                    is_superuser=True,
                    extra_metadata={"is_default": True},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 默认管理员创建成功: admin")
            print("   邮箱: admin@default.com")
            print("   密码: Admin123!@#")

        result = await conn.execute(
            select(Workspace).where(
                Workspace.tenant_id == tenant_id,
                Workspace.name == "默认工作空间"
            )
        )
        existing_workspace = result.scalar_one_or_none()

        if existing_workspace:
            print("✅ 默认工作空间已存在")
        else:
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
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 默认工作空间创建成功: {workspace_id}")

            member_id = str(uuid4())
            await conn.execute(
                insert(WorkspaceMember).values(
                    id=member_id,
                    workspace_id=workspace_id,
                    user_id=admin_user_id,
                    role="owner",
                    joined_at=datetime.utcnow()
                )
            )
            print(f"✅ 管理员添加到默认工作空间")

        # 创建系统租户和系统模板工作空间
        system_tenant_result = await conn.execute(
            select(Tenant).where(Tenant.name == "__system__")
        )
        existing_system_tenant = system_tenant_result.scalar_one_or_none()

        if existing_system_tenant:
            print("✅ 系统租户已存在")
            system_tenant_id = existing_system_tenant.id
        else:
            system_tenant_id = str(uuid4())
            await conn.execute(
                insert(Tenant).values(
                    id=system_tenant_id,
                    name="__system__",
                    contact_email="system@internal",
                    plan="enterprise",
                    status="active",
                    extra_metadata={"is_system": True},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 系统租户创建成功: {system_tenant_id}")

        # 创建系统模板工作空间（在系统租户下）
        template_workspace_result = await conn.execute(
            select(Workspace).where(
                Workspace.tenant_id == system_tenant_id,
                Workspace.name == "__system_template__"
            )
        )
        existing_template_workspace = template_workspace_result.scalar_one_or_none()

        if existing_template_workspace:
            print("✅ 系统模板工作空间已存在")
            template_workspace_id = existing_template_workspace.id
        else:
            template_workspace_id = str(uuid4())
            await conn.execute(
                insert(Workspace).values(
                    id=template_workspace_id,
                    tenant_id=system_tenant_id,
                    name="__system_template__",
                    description="系统公共知识库模板工作空间",
                    is_default=False,
                    extra_metadata={"is_system_template": True},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 系统模板工作空间创建成功: {template_workspace_id}")

            # 创建系统模板知识库
            from infrastructure.database.models import Dataset
            template_dataset_id = str(uuid4())
            await conn.execute(
                insert(Dataset).values(
                    id=template_dataset_id,
                    workspace_id=template_workspace_id,
                    name="系统模板知识库",
                    description="系统公共知识库模板",
                    is_public=True,
                    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
                    chunk_size=500,
                    chunk_overlap=50,
                    extra_metadata={"is_system_template": True},
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            print(f"✅ 系统模板知识库创建成功: {template_dataset_id}")

    print("\n🎉 数据库初始化完成！")


if __name__ == "__main__":
    asyncio.run(init_database())