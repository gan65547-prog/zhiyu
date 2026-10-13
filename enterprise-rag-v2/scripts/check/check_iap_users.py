import asyncio
from infrastructure.database.session import get_db_context
from infrastructure.database.models import User
from sqlalchemy import select

async def check_iap_users():
    async with get_db_context() as session:
        # 检查iapadmin和iapuser1的用户信息
        result = await session.execute(
            select(User)
            .where(User.username.in_(["iapadmin", "iapuser1"]))
        )
        users = result.scalars().all()
        
        print("iapadmin和iapuser1用户信息:")
        for user in users:
            print(f"用户: {user.username} ({user.email})")
            print(f"  租户ID: {user.tenant_id}")
            print(f"  激活状态: {user.is_active}")
            print(f"  超级管理员: {user.is_superuser}")
            print(f"  密码哈希: {user.hashed_password}")
            print()

if __name__ == "__main__":
    asyncio.run(check_iap_users())