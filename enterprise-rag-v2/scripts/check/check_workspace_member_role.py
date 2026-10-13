import asyncio
from infrastructure.database.session import get_db_context
from infrastructure.database.models import WorkspaceMember
from sqlalchemy import select

async def check_workspace_member_role():
    async with get_db_context() as session:
        # 检查工作空间成员的角色存储值
        result = await session.execute(
            select(WorkspaceMember)
            .limit(5)
        )
        members = result.scalars().all()
        
        print("工作空间成员角色存储值:")
        for member in members:
            print(f"  成员ID: {member.id}")
            print(f"  用户ID: {member.user_id}")
            print(f"  工作空间ID: {member.workspace_id}")
            print(f"  角色: {member.role}")
            print(f"  角色类型: {type(member.role)}")
            print()

if __name__ == "__main__":
    async def run():
        try:
            await check_workspace_member_role()
        except Exception as e:
            print(f"Error: {e}")
    asyncio.run(run())