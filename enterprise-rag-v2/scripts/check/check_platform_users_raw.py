import asyncio
from sqlalchemy import text
from infrastructure.database.session import AsyncSessionLocal

async def check_platform_users():
    async with AsyncSessionLocal() as session:
        # 检查platform_users表的结构
        print('=== platform_users table structure ===')
        structure_query = text("PRAGMA table_info(platform_users)")
        structure_result = await session.execute(structure_query)
        for row in structure_result:
            print(f'Column: {row[1]}, Type: {row[2]}, Null: {row[3]}, Default: {row[4]}')
        
        # 检查platform_users表的数据
        print('\n=== platform_users table data ===')
        data_query = text("SELECT id, platform, platform_user_id, system_user_id, tenant_id, app_config_id FROM platform_users LIMIT 10")
        data_result = await session.execute(data_query)
        for row in data_result:
            print(f'ID: {row[0]}, Platform: {row[1]}, Platform User ID: {row[2]}')
            print(f'  System User ID: {row[3]}, Tenant ID: {row[4]}')
            print(f'  App Config ID: {row[5]}')
            print()

if __name__ == '__main__':
    asyncio.run(check_platform_users())
