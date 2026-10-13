#!/usr/bin/env python3
"""
创建默认工作空间
"""

import sys
sys.path.insert(0, '/Users/gan/Documents/ganfy/enterprise-rag-v2')

import asyncio
from uuid import uuid4
from datetime import datetime
from sqlalchemy import select, insert

from infrastructure.database.session import engine, AsyncSessionLocal
from infrastructure.database.models import Base, Workspace, WorkspaceMember, User, Tenant


async def create_default_workspace():
    """创建默认工作空间"""
    async with AsyncSessionLocal() as session:
        # 获取管理员用户
        result = await session.execute(
            select(User).where(User.email == "admin@default.com")
        )
        admin_user = result.scalar_one_or_none()
        
        if not admin_user:
            print("❌ 管理员用户不存在")
            return
        
        print(f"✅ 找到管理员用户: {admin_user.username} ({admin_user.email})")
        
        # 检查是否已有工作空间
        result = await session.execute(
            select(Workspace).where(Workspace.tenant_id == admin_user.tenant_id)
        )
        existing_workspace = result.scalar_one_or_none()
        
        if existing_workspace:
            print(f"✅ 工作空间已存在: {existing_workspace.name}")
            return
        
        # 创建默认工作空间
        workspace_id = uuid4()
        await session.execute(
            insert(Workspace).values(
                id=str(workspace_id),
                tenant_id=str(admin_user.tenant_id),
                name="默认工作空间",
                description="系统默认工作空间",
                extra_metadata={"is_default": True},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
        
        # 添加管理员为工作空间成员
        await session.execute(
            insert(WorkspaceMember).values(
                id=str(uuid4()),
                workspace_id=str(workspace_id),
                user_id=str(admin_user.id),
                role="owner",
                joined_at=datetime.utcnow()
            )
        )
        
        await session.commit()
        
        print(f"✅ 默认工作空间创建成功: {workspace_id}")
        print(f"✅ 管理员已添加为工作空间所有者")


if __name__ == "__main__":
    asyncio.run(create_default_workspace())
