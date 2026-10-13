from infrastructure.database.session import engine
from infrastructure.database.models import User
import asyncio

async def check_user():
    async with engine.begin() as conn:
        from sqlalchemy import select
        # 选择所有列
        result = await conn.execute(select(User))
        users = result.fetchall()
        print(f'Number of users: {len(users)}')
        for user in users:
            print(f'User: {user}')
            print(f'User type: {type(user)}')
            if hasattr(user, '__dict__'):
                print(f'User attributes: {user.__dict__}')
            else:
                # 如果是元组或其他类型，直接打印
                print(f'User data: {user}')
        
        # 检查特定用户
        result = await conn.execute(select(User).where(User.email == 'superadmin@system.com'))
        user = result.scalar_one_or_none()
        print(f'\nChecking superadmin@system.com:')
        print(f'User exists: {user is not None}')
        if user:
            print(f'User data: {user}')

if __name__ == '__main__':
    asyncio.run(check_user())