import asyncio
from infrastructure.database.session import get_db_context
from infrastructure.database.models import User, Workspace, WorkspaceMember, WorkspaceRole
from sqlalchemy import select, join

async def check_user_workspaces():
    async with get_db_context() as session:
        # 检查iapadmin的工作空间成员关系
        result = await session.execute(
            select(User, Workspace, WorkspaceMember)
            .join(WorkspaceMember, User.id == WorkspaceMember.user_id)
            .join(Workspace, WorkspaceMember.workspace_id == Workspace.id)
            .where(User.username == "iapadmin")
        )
        user_workspaces = result.all()
        
        print("iapadmin的工作空间成员关系:")
        if not user_workspaces:
            print("  该用户不是任何工作空间的成员")
        else:
            for user, workspace, member in user_workspaces:
                print(f"  工作空间: {workspace.name} (ID: {workspace.id})")
                print(f"  角色: {member.role}")
                print()

if __name__ == "__main__":
    asyncio.run(check_user_workspaces())