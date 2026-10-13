#!/usr/bin/env python3
"""测试聊天功能"""

import httpx
import json

async def test_chat():
    """测试聊天功能"""
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
        
        # 测试获取会话列表
        conversations_url = "http://localhost:8000/api/v1/chat/conversations"
        conversations_response = await client.get(
            conversations_url,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        print(f"\nConversations status: {conversations_response.status_code}")
        print(f"Conversations: {conversations_response.json()}")
        
        # 测试聊天
        chat_url = "http://localhost:8000/api/v1/chat/"
        chat_data = {
            "dataset_id": "0e004273-2bf8-4f9d-8139-d80791a2f718",
            "query": "你好，测试聊天功能",
            "retrieval_mode": "semantic",
            "top_k": 3,
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        try:
            chat_response = await client.post(
                chat_url,
                json=chat_data,
                headers={"Authorization": f"Bearer {token}"}
            )
            print(f"\nChat status: {chat_response.status_code}")
            print(f"Chat response: {chat_response.json()}")
        except Exception as e:
            print(f"\nChat error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_chat())
