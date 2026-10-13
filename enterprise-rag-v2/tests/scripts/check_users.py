#!/usr/bin/env python3
"""检查数据库中的用户数据"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from infrastructure.database.session import AsyncSessionLocal
from infrastructure.database.models import User, Tenant
from sqlalchemy import select


async def check_users():
    """检查数据库中的用户数据"""
    async with AsyncSessionLocal() as session:
        # 检查租户
        print("=== 租户列表 ===")
        tenants = await session.execute(select(Tenant))
        for tenant in tenants.scalars():
            print(f"租户: {tenant.name} (ID: {tenant.id})")
            print(f"  邮箱: {tenant.contact_email}")
            print(f"  状态: {tenant.status}")
            print()
        
        # 检查用户
        print("=== 用户列表 ===")
        users = await session.execute(select(User))
        for user in users.scalars():
            print(f"用户: {user.username} (ID: {user.id})")
            print(f"  邮箱: {user.email}")
            print(f"  租户ID: {user.tenant_id}")
            print(f"  激活状态: {user.is_active}")
            print(f"  超级用户: {user.is_superuser}")
            print()


if __name__ == "__main__":
    asyncio.run(check_users())
