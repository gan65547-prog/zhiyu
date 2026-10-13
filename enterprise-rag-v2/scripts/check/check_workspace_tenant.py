import asyncio
from infrastructure.database.session import get_db_context
from infrastructure.database.models import User, Workspace, WorkspaceMember
from sqlalchemy import select, join

async def check_workspace_tenant():
    async with get_db_context() as session:
        # 查找iapadmin用户
        user_result = await session.execute(
            select(User)
            .where(User.username == "iapadmin")
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("iapadmin用户不存在")
            return
        
        print(f"iapadmin用户信息:")
        print(f"  用户ID: {user.id}")
        print(f"  租户ID: {user.tenant_id}")
        print()
        
        # 查找iapadmin的工作空间及其租户ID
        member_result = await session.execute(
            select(WorkspaceMember, Workspace.name, Workspace.tenant_id)
            .join(Workspace, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user.id)
        )
        members = member_result.all()
        
        print("iapadmin的工作空间及其租户ID:")
        if not members:
            print("  该用户不是任何工作空间的成员")
        else:
            for member, workspace_name, workspace_tenant_id in members:
                print(f"  工作空间: {workspace_name}")
                print(f"  工作空间租户ID: {workspace_tenant_id}")
                print(f"  用户租户ID: {user.tenant_id}")
                print(f"  租户ID匹配: {workspace_tenant_id == user.tenant_id}")
                print()

if __name__ == "__main__":
    asyncio.run(check_workspace_tenant())