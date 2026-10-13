#!/usr/bin/env python3
"""
修复CORS和API错误的脚本

解决问题：
1. CORS跨域问题
2. 用户没有tenant_id导致的500错误
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, update
from infrastructure.database.session import AsyncSessionLocal
from infrastructure.database.models import User, Tenant


async def fix_users_tenant_id():
    """修复用户的tenant_id"""
    async with AsyncSessionLocal() as session:
        # 获取所有没有tenant_id的用户
        result = await session.execute(
            select(User).where(User.tenant_id == None)
        )
        users_without_tenant = result.scalars().all()
        
        if not users_without_tenant:
            print("✅ 所有用户都有tenant_id")
            return
        
        print(f"发现 {len(users_without_tenant)} 个用户没有tenant_id")
        
        # 获取或创建默认租户
        tenant_result = await session.execute(
            select(Tenant).where(Tenant.name == "默认租户")
        )
        default_tenant = tenant_result.scalar_one_or_none()
        
        if not default_tenant:
            print("创建默认租户...")
            default_tenant = Tenant(
                name="默认租户",
                contact_email="admin@example.com",
                plan="free",
                status="active"
            )
            session.add(default_tenant)
            await session.flush()
            print(f"✅ 创建默认租户: {default_tenant.id}")
        
        # 更新所有没有tenant_id的用户
        for user in users_without_tenant:
            user.tenant_id = str(default_tenant.id)
            print(f"  - 更新用户 {user.username} 的tenant_id")
        
        await session.commit()
        print(f"✅ 已修复 {len(users_without_tenant)} 个用户的tenant_id")


async def check_cors_config():
    """检查CORS配置"""
    from core.config import get_settings
    
    settings = get_settings()
    print("\n当前CORS配置:")
    print(f"  允许的源: {settings.security.allowed_origins}")
    
    if "http://localhost:3000" not in settings.security.allowed_origins:
        print("⚠️  警告: http://localhost:3000 不在允许的源列表中")
        print("   请在 .env 文件中添加:")
        print("   ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001")
    else:
        print("✅ CORS配置正确")


async def main():
    """主函数"""
    print("=" * 60)
    print("修复CORS和API错误")
    print("=" * 60)
    
    print("\n1. 检查CORS配置...")
    await check_cors_config()
    
    print("\n2. 修复用户tenant_id...")
    await fix_users_tenant_id()
    
    print("\n" + "=" * 60)
    print("修复完成！")
    print("=" * 60)
    print("\n请重启后端服务以应用更改")


if __name__ == "__main__":
    asyncio.run(main())
