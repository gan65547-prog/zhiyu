#!/usr/bin/env python3
"""创建默认工作空间和工作空间成员"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from uuid import uuid4
from datetime import datetime, UTC
from infrastructure.database.session import AsyncSessionLocal
from infrastructure.database.models import Workspace, WorkspaceMember, Tenant, User
from sqlalchemy import select


async def create_default_workspace():
    """创建默认工作空间和工作空间成员"""
    async with AsyncSessionLocal() as session:
        # 获取默认租户
        tenant_result = await session.execute(
            select(Tenant).where(Tenant.contact_email == "admin@default.com")
        )
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            print("错误：未找到默认租户")
            return
        
        # 获取默认管理员用户
        user_result = await session.execute(
            select(User).where(User.email == "admin@default.com")
        )
        user = user_result.scalar_one_or_none()
        if not user:
            print("错误：未找到默认管理员用户")
            return
        
        # 检查是否已有工作空间
        workspace_result = await session.execute(
            select(Workspace).where(Workspace.tenant_id == tenant.id)
        )
        existing_workspace = workspace_result.scalar_one_or_none()
        
        if existing_workspace:
            print(f"工作空间已存在: {existing_workspace.name} (ID: {existing_workspace.id})")
            workspace = existing_workspace
        else:
            # 创建默认工作空间
            workspace = Workspace(
                id=str(uuid4()),
                tenant_id=tenant.id,
                name="默认工作空间",
                description="系统默认工作空间",
                extra_metadata={"is_default": True},
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            session.add(workspace)
            await session.flush()
            print(f"创建默认工作空间: {workspace.name} (ID: {workspace.id})")
        
        # 检查是否已有工作空间成员
        member_result = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.user_id == user.id
            )
        )
        existing_member = member_result.scalar_one_or_none()
        
        if existing_member:
            print(f"工作空间成员已存在: {user.username} -> {workspace.name}")
        else:
            # 创建工作空间成员
            member = WorkspaceMember(
                id=str(uuid4()),
                workspace_id=workspace.id,
                user_id=user.id,
                role="owner",
                joined_at=datetime.now(UTC)
            )
            session.add(member)
            await session.flush()
            print(f"创建工作空间成员: {user.username} -> {workspace.name} (角色: owner)")
        
        await session.commit()
        print("\n✅ 工作空间初始化完成！")


if __name__ == "__main__":
    asyncio.run(create_default_workspace())
