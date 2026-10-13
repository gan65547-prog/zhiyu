import asyncio
from infrastructure.database.session import get_db_context
from infrastructure.database.models import User, WorkspaceMember, WorkspaceRole
from sqlalchemy import select, and_

async def check_iapadmin_roles():
    async with get_db_context() as session:
        # 查找iapadmin用户
        result = await session.execute(
            select(User)
            .where(User.username == "iapadmin")
        )
        user = result.scalar_one_or_none()
        
        if user:
            print(f"User: {user.username}, ID: {user.id}")
            
            # 查找用户的工作空间成员关系
            result = await session.execute(
                select(WorkspaceMember)
                .where(WorkspaceMember.user_id == str(user.id))
            )
            members = result.scalars().all()
            
            print(f"Workspace members: {len(members)}")
            for member in members:
                print(f"  Workspace ID: {member.workspace_id}, Role: {member.role}, Type: {type(member.role)}")
                print(f"  Role value: {member.role.value if hasattr(member.role, 'value') else member.role}")

if __name__ == "__main__":
    asyncio.run(check_iapadmin_roles())