import asyncio
from infrastructure.database.session import get_db_context
from infrastructure.database.models import User, WorkspaceMember, Workspace
from sqlalchemy import select, join

async def check_iapadmin_workspaces():
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
        print(f"  用户名: {user.username}")
        print(f"  邮箱: {user.email}")
        print(f"  租户ID: {user.tenant_id}")
        print(f"  超级管理员: {user.is_superuser}")
        print()
        
        # 查找iapadmin的工作空间成员关系
        member_result = await session.execute(
            select(WorkspaceMember, Workspace.name)
            .join(Workspace, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user.id)
        )
        members = member_result.all()
        
        print("iapadmin的工作空间成员关系:")
        if not members:
            print("  该用户不是任何工作空间的成员")
        else:
            for member, workspace_name in members:
                print(f"  工作空间: {workspace_name}")
                print(f"  角色: {member.role}")
                print(f"  角色类型: {type(member.role)}")
                print()

if __name__ == "__main__":
    asyncio.run(check_iapadmin_workspaces())