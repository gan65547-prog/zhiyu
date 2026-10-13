import asyncio
from infrastructure.database.session import AsyncSessionLocal
from sqlalchemy import select
from infrastructure.database.models import Dataset, Workspace

async def check_data():
    async with AsyncSessionLocal() as session:
        print('=== Workspaces ===')
        result = await session.execute(select(Workspace))
        for row in result.scalars():
            print(f'ID: {row.id}, Tenant ID: {row.tenant_id}, Name: {row.name}')
        
        print('\n=== Datasets ===')
        result = await session.execute(select(Dataset))
        for row in result.scalars():
            print(f'ID: {row.id}, Workspace ID: {row.workspace_id}, Name: {row.name}')

if __name__ == '__main__':
    asyncio.run(check_data())
