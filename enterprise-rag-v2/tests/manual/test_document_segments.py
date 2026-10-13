#!/usr/bin/env python3
"""测试文档分段API"""

import httpx
import json

async def test_document_segments():
    """测试文档分段API"""
    # 先获取token
    login_url = "http://localhost:8000/api/v1/auth/login"
    login_data = {
        "email": "admin@default.com",
        "password": "Admin123!@#"
    }
    
    async with httpx.AsyncClient() as client:
        # 登录获取token
        login_response = await client.post(login_url, json=login_data)
        print(f"Login status: {login_response.status_code}")
        
        if login_response.status_code != 200:
            print("登录失败")
            return
        
        token = login_response.json()['data']['access_token']
        
        # 测试获取文档分段 - 使用错误的文档ID
        document_id = "59e526e6-56c1-42e6-bd29-a2ed81a7d018"
        segments_url = f"http://localhost:8000/api/v1/documents/{document_id}/segments"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        segments_response = await client.get(
            segments_url,
            headers=headers
        )
        
        print(f"\nGet segments status: {segments_response.status_code}")
        try:
            print(f"Get segments response: {segments_response.json()}")
        except:
            print(f"Get segments response: {segments_response.text}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_document_segments())
