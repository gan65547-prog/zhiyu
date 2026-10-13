import asyncio
from infrastructure.database.session import get_db_context
from infrastructure.database.models import WorkspaceMember
from sqlalchemy import select

async def check_role_values():
    async with get_db_context() as session:
        # 检查工作空间成员的角色值
        result = await session.execute(
            select(WorkspaceMember.role)
            .limit(10)
        )
        roles = result.scalars().all()
        
        print("工作空间成员角色值:")
        for i, role in enumerate(roles):
            print(f"  {i+1}. 角色: {role}")
            print(f"    类型: {type(role)}")
            print(f"    值: {role.value if hasattr(role, 'value') else role}")
            print()

if __name__ == "__main__":
    asyncio.run(check_role_values())