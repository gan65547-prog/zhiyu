#!/usr/bin/env python3
"""
测试 PlatformAppConfigService.get_config_by_app_id 方法
"""

import asyncio
import sys
import os

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.abspath('.'))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from apps.integration.services.platform_app_config import PlatformAppConfigService

DATABASE_URL = "sqlite+aiosqlite:///./enterprise_rag.db"

async def test_get_config():
    # 创建数据库引擎
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # 创建服务实例
        service = PlatformAppConfigService(db=session, redis=None)
        
        # 测试 get_config_by_app_id
        platform = "feishu"
        app_id = "cli_a95e1f6a30389cca"
        
        print(f"测试 get_config_by_app_id: platform={platform}, app_id={app_id}")
        try:
            config = await service.get_config_by_app_id(platform, app_id)
            if config:
                print(f"✅ 配置获取成功:")
                print(f"   id: {config.get('id')}")
                print(f"   tenant_id: {config.get('tenant_id')}")
                print(f"   platform: {config.get('platform')}")
                print(f"   app_id: {config.get('app_id')}")
                print(f"   凭证存在: {'credentials' in config}")
                if 'credentials' in config:
                    print(f"   app_secret 存在: {'app_secret' in config['credentials']}")
            else:
                print("❌ 配置获取失败")
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_get_config())