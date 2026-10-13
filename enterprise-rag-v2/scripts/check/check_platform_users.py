import asyncio
from infrastructure.database.session import AsyncSessionLocal
from sqlalchemy import select
from infrastructure.database.models import PlatformUser

async def check_platform_users():
    async with AsyncSessionLocal() as session:
        print('=== Platform Users ===')
        result = await session.execute(select(PlatformUser))
        for row in result.scalars():
            print(f'ID: {row.id}, Platform: {row.platform}, Platform User ID: {row.platform_user_id}')
            print(f'  System User ID: {row.system_user_id}, Tenant ID: {row.tenant_id}')
            print(f'  App Config ID: {row.app_config_id}')
            print()

if __name__ == '__main__':
    asyncio.run(check_platform_users())
