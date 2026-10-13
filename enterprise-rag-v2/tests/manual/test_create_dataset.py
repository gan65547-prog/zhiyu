#!/usr/bin/env python3
"""测试创建数据集"""

import httpx
import json

async def test_create_dataset():
    """测试创建数据集"""
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
        print(f"Login response: {login_response.json()}")
        
        if login_response.status_code != 200:
            print("登录失败")
            return
        
        token = login_response.json()['data']['access_token']
        
        # 创建数据集
        dataset_url = "http://localhost:8000/api/v1/datasets/"
        dataset_data = {
            "name": "测试数据集",
            "description": "测试用数据集"
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        dataset_response = await client.post(
            dataset_url,
            json=dataset_data,
            headers=headers
        )
        
        print(f"\nCreate dataset status: {dataset_response.status_code}")
        print(f"Create dataset response: {dataset_response.json()}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_create_dataset())
