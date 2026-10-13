import asyncio
from infrastructure.database.session import engine
from infrastructure.database.models import Base

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print('数据库表已创建')

asyncio.run(create_tables())