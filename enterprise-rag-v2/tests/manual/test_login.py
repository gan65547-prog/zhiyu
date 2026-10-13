#!/usr/bin/env python3
"""测试前端登录请求"""

import httpx
import json

async def test_frontend_login():
    """模拟前端登录请求"""
    url = "http://localhost:8000/api/v1/auth/login"
    
    # 测试1: 正确的邮箱和密码
    print("=== 测试1: 正确的邮箱和密码 ===")
    data = {
        "email": "admin@default.com",
        "password": "Admin123!@#"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
                "Origin": "http://localhost:3000"
            }
        )
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        print()
    
    # 测试2: 错误的邮箱
    print("=== 测试2: 错误的邮箱 ===")
    data = {
        "email": "wrong@example.com",
        "password": "Admin123!@#"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=data,
            headers={
                "Content-Type": "application/json"
            }
        )
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        print()
    
    # 测试3: 错误的密码
    print("=== 测试3: 错误的密码 ===")
    data = {
        "email": "admin@default.com",
        "password": "wrongpassword"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=data,
            headers={
                "Content-Type": "application/json"
            }
        )
        
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_frontend_login())
