#!/usr/bin/env python3
"""测试CORS配置"""

import httpx

async def test_cors():
    """测试CORS配置"""
    url = "http://localhost:8000/api/v1/documents/59e526e6-56c1-42e6-bd29-a2ed81a7d018/segments"
    
    async with httpx.AsyncClient() as client:
        # 测试带Origin头的请求
        response = await client.get(
            url,
            headers={
                "Origin": "http://localhost:3000",
                "Authorization": "Bearer $(curl -s -X POST http://localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' -d '{\"email\": \"admin@default.com\", \"password\": \"Admin123!@#\"}' | jq -r '.data.access_token)"
            }
        )
        
        print(f"Status code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response: {response.json()}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_cors())
