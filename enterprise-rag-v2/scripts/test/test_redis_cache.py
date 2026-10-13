#!/usr/bin/env python3
"""
测试RedisCache类的读写操作
"""

import asyncio
from infrastructure.cache import get_cache

async def test_redis_cache():
    """测试RedisCache类读写"""
    print("测试RedisCache类...")
    
    # 使用RedisCache类
    cache = await get_cache()
    
    try:
        # 测试设置值
        success = await cache.set('health_check', 'ok', ttl=10)
        print(f"✓ 成功设置值: {success}")
        
        # 测试获取值
        value = await cache.get('health_check')
        print(f"✓ 成功获取值: {value}")
        
        # 验证值是否正确
        if value == 'ok':
            print("✓ 读写匹配，RedisCache工作正常")
        else:
            print(f"✗ 读写不匹配: 期望 'ok'，实际 '{value}'")
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    finally:
        await cache.close()

if __name__ == "__main__":
    asyncio.run(test_redis_cache())
