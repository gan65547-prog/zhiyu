import asyncio
from infrastructure.database.session import get_db_context
from infrastructure.database.models import User, Tenant
from sqlalchemy import select, join

async def check_user_tenant():
    async with get_db_context() as session:
        # 检查iapadmin和iapuser1的租户信息
        result = await session.execute(
            select(User, Tenant)
            .join(Tenant, User.tenant_id == Tenant.id)
            .where(User.username.in_(["iapadmin", "iapuser1"]))
        )
        users_with_tenant = result.all()
        
        print("用户租户信息:")
        for user, tenant in users_with_tenant:
            print(f"用户: {user.username} ({user.email})")
            print(f"  租户: {tenant.name} (ID: {tenant.id})")
            print(f"  租户管理员: {user.is_superuser}")
            print()

if __name__ == "__main__":
    asyncio.run(check_user_tenant())