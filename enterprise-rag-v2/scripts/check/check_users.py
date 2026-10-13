import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from infrastructure.database.session import engine
from infrastructure.database.models import User

async def check_users():
    """检查用户列表"""
    print("用户列表:")
    print("-" * 80)
    
    async with engine.begin() as conn:
        result = await conn.execute(User.__table__.select())
        users = result.fetchall()
        
        for user in users:
            print(f"ID: {user.id}")
            print(f"用户名: {user.username}")
            print(f"邮箱: {user.email}")
            print(f"活跃状态: {user.is_active}")
            print(f"超级管理员: {user.is_superuser}")
            print("-" * 80)

if __name__ == "__main__":
    asyncio.run(check_users())