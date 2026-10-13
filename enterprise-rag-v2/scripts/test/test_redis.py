#!/usr/bin/env python3
"""
测试Redis缓存读写操作
"""

import asyncio
import redis.asyncio as redis

async def test_redis():
    """测试Redis缓存读写"""
    print("测试Redis缓存...")
    
    # 直接使用redis客户端
    client = redis.Redis(decode_responses=True)
    
    try:
        # 测试设置值
        await client.set('health_check', 'ok', ex=10)
        print("✓ 成功设置值")
        
        # 测试获取值
        value = await client.get('health_check')
        print(f"✓ 成功获取值: {value}")
        
        # 验证值是否正确
        if value == 'ok':
            print("✓ 读写匹配，Redis工作正常")
        else:
            print(f"✗ 读写不匹配: 期望 'ok'，实际 '{value}'")
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_redis())
