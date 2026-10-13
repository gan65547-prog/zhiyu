#!/usr/bin/env python3
"""测试并发请求，验证500错误是否已修复"""

import asyncio
import aiohttp
import time

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NzY0YTUwYy03MDI4LTQ2ZjYtOTkxMy1kYzM0MTcyMjdiY2MiLCJ1c2VybmFtZSI6InN1cGVyYWRtaW4iLCJlbWFpbCI6InN1cGVyYWRtaW5Ac3lzdGVtLmNvbSIsInRlbmFudF9pZCI6IjEwNjkxNmVlLTlmYWItNDBiZS1hNDM5LTQxNzY0OTU0YWRmZSIsImlzX3N1cGVydXNlciI6dHJ1ZSwiZXhwIjoxNzc1NjU1NzEyLCJ0eXBlIjoiYWNjZXNzIiwiaWF0IjoxNzc1NjU0ODEyfQ.Ng_9Kuwt_tloORc8Rsj3m1YwjTL7BW-wi1inI4LZsSw"

API_ENDPOINTS = [
    "http://localhost:8000/api/v1/datasets/",
    "http://localhost:8000/api/v1/workspaces/current"
]

async def make_request(session, url):
    """发送单个请求"""
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        start_time = time.time()
        async with session.get(url, headers=headers) as response:
            status = response.status
            data = await response.json()
            end_time = time.time()
            print(f"{url} - Status: {status}, Time: {end_time - start_time:.2f}s")
            if status != 200:
                print(f"  Error: {data}")
            return status
    except Exception as e:
        print(f"{url} - Error: {e}")
        return 500

async def test_concurrent_requests():
    """测试并发请求"""
    print("开始测试并发请求...")
    print(f"测试的API端点: {API_ENDPOINTS}")
    print(f"使用的Token: {TOKEN[:20]}...")
    print()
    
    async with aiohttp.ClientSession() as session:
        # 测试1: 5个并发请求
        print("=== 测试1: 5个并发请求 ===")
        tasks = []
        for i in range(5):
            for url in API_ENDPOINTS:
                tasks.append(make_request(session, url))
        
        results = await asyncio.gather(*tasks)
        success_count = sum(1 for status in results if status == 200)
        total_count = len(results)
        print(f"成功: {success_count}/{total_count}")
        print()
        
        # 测试2: 10个并发请求（模拟多次刷新）
        print("=== 测试2: 10个并发请求 ===")
        tasks = []
        for i in range(10):
            for url in API_ENDPOINTS:
                tasks.append(make_request(session, url))
        
        results = await asyncio.gather(*tasks)
        success_count = sum(1 for status in results if status == 200)
        total_count = len(results)
        print(f"成功: {success_count}/{total_count}")
        print()
        
        # 测试3: 连续3次批量请求（模拟连续刷新）
        print("=== 测试3: 连续3次批量请求 ===")
        for batch in range(3):
            print(f"批处理 {batch + 1}:")
            tasks = []
            for url in API_ENDPOINTS:
                tasks.append(make_request(session, url))
            results = await asyncio.gather(*tasks)
            success_count = sum(1 for status in results if status == 200)
            total_count = len(results)
            print(f"  成功: {success_count}/{total_count}")
            await asyncio.sleep(0.5)  # 短暂休息

if __name__ == "__main__":
    asyncio.run(test_concurrent_requests())
