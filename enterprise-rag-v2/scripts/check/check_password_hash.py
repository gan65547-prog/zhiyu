import asyncio
from infrastructure.database.session import get_db_context
from infrastructure.database.models import User
from sqlalchemy import select
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def check_password_hash():
    async with get_db_context() as session:
        # 检查用户密码哈希
        result = await session.execute(
            select(User)
            .where(User.username.in_(["iapadmin", "superadmin"]))
        )
        users = result.scalars().all()
        
        print("用户密码哈希检查:")
        for user in users:
            print(f"用户: {user.username} ({user.email})")
            print(f"  密码哈希: {user.hashed_password}")
            print(f"  尝试验证 '123456': {pwd_context.verify('123456', user.hashed_password)}")
            print(f"  尝试验证 'Password123!@#': {pwd_context.verify('Password123!@#', user.hashed_password)}")
            print(f"  尝试验证 'SuperAdmin123!@#': {pwd_context.verify('SuperAdmin123!@#', user.hashed_password)}")
            print()

if __name__ == "__main__":
    asyncio.run(check_password_hash())