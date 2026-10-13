import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import bcrypt
from sqlalchemy import update

from infrastructure.database.session import engine
from infrastructure.database.models import User

async def update_user_passwords():
    """更新用户密码"""
    print("开始更新用户密码...")
    
    async with engine.begin() as conn:
        # 超级管理员
        hashed_pw = bcrypt.hashpw("SuperAdmin123!@#".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        await conn.execute(
            update(User).where(User.email == "superadmin@system.com").values(hashed_password=hashed_pw)
        )
        print("✅ 更新超级管理员密码: SuperAdmin123!@#")
        
        # 张三
        hashed_pw = bcrypt.hashpw("Zhangsan123!@#".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        await conn.execute(
            update(User).where(User.email == "zhangsan@abctech.com").values(hashed_password=hashed_pw)
        )
        print("✅ 更新张三密码: Zhangsan123!@#")
        
        # 李四
        hashed_pw = bcrypt.hashpw("Lisi123!@#".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        await conn.execute(
            update(User).where(User.email == "lisi@abctech.com").values(hashed_password=hashed_pw)
        )
        print("✅ 更新李四密码: Lisi123!@#")
        
        # 王五
        hashed_pw = bcrypt.hashpw("Wangwu123!@#".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        await conn.execute(
            update(User).where(User.email == "wangwu@abctech.com").values(hashed_password=hashed_pw)
        )
        print("✅ 更新王五密码: Wangwu123!@#")
        
        # 赵六
        hashed_pw = bcrypt.hashpw("Zhaoliu123!@#".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        await conn.execute(
            update(User).where(User.email == "zhaoliu@abctech.com").values(hashed_password=hashed_pw)
        )
        print("✅ 更新赵六密码: Zhaoliu123!@#")
    
    print("\n🎉 密码更新完成！")

if __name__ == "__main__":
    asyncio.run(update_user_passwords())