#!/usr/bin/env python3
"""检查工作空间和工作空间成员数据"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from infrastructure.database.session import AsyncSessionLocal
from infrastructure.database.models import Workspace, WorkspaceMember, User
from sqlalchemy import select


async def check_workspaces():
    """检查工作空间和工作空间成员数据"""
    async with AsyncSessionLocal() as session:
        # 检查工作空间
        print("=== 工作空间列表 ===")
        workspaces = await session.execute(select(Workspace))
        for workspace in workspaces.scalars():
            print(f"工作空间: {workspace.name} (ID: {workspace.id})")
            print(f"  租户ID: {workspace.tenant_id}")
            print(f"  创建时间: {workspace.created_at}")
            print()
        
        # 检查工作空间成员
        print("=== 工作空间成员列表 ===")
        members = await session.execute(
            select(WorkspaceMember, User.username, Workspace.name)
            .join(User, WorkspaceMember.user_id == User.id)
            .join(Workspace, WorkspaceMember.workspace_id == Workspace.id)
        )
        for member, username, workspace_name in members.all():
            print(f"用户: {username} -> 工作空间: {workspace_name}")
            print(f"  成员ID: {member.id}")
            print(f"  角色: {member.role}")
            print(f"  加入时间: {member.joined_at}")
            print()


if __name__ == "__main__":
    asyncio.run(check_workspaces())
