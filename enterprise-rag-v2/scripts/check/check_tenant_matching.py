import asyncio
from sqlalchemy import text
from infrastructure.database.session import AsyncSessionLocal

async def check_tenant_matching():
    async with AsyncSessionLocal() as session:
        # 检查workspaces表中的tenant_id
        print('=== Workspaces with tenant_id ===')
        workspace_query = text("SELECT id, name, tenant_id FROM workspaces")
        workspace_result = await session.execute(workspace_query)
        for row in workspace_result:
            print(f'Workspace ID: {row[0]}, Name: {row[1]}, Tenant ID: {row[2]}')
        
        # 检查platform_users表中的tenant_id
        print('\n=== Platform Users with tenant_id ===')
        user_query = text("SELECT id, platform, platform_user_id, tenant_id FROM platform_users")
        user_result = await session.execute(user_query)
        for row in user_result:
            print(f'User ID: {row[0]}, Platform: {row[1]}, Platform User ID: {row[2]}, Tenant ID: {row[3]}')

if __name__ == '__main__':
    asyncio.run(check_tenant_matching())
