import asyncio
from infrastructure.database.session import AsyncSessionLocal, get_db_context
from infrastructure.database.models import Workspace, WorkspaceMember, User
from sqlalchemy import select

async def check_data():
    async with get_db_context() as session:
        # Check users
        result = await session.execute(select(User))
        users = result.scalars().all()
        print(f'Users: {len(users)}')
        for user in users:
            print(f'  - {user.username} ({user.email})')
        
        # Check workspaces
        result = await session.execute(select(Workspace))
        workspaces = result.scalars().all()
        print(f'\nWorkspaces: {len(workspaces)}')
        for workspace in workspaces:
            print(f'  - {workspace.name} (ID: {workspace.id})')
        
        # Check workspace members
        result = await session.execute(select(WorkspaceMember))
        members = result.scalars().all()
        print(f'\nWorkspace members: {len(members)}')
        for member in members:
            print(f'  - User: {member.user_id}, Workspace: {member.workspace_id}, Role: {member.role}')

if __name__ == "__main__":
    asyncio.run(check_data())