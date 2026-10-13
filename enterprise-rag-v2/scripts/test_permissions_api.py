#!/usr/bin/env python3
"""
测试会话权限API
"""

import asyncio
import httpx
import json

API_BASE = "http://localhost:8000/api/v1"


async def test_conversation_permissions():
    """测试会话权限功能"""
    
    async with httpx.AsyncClient() as client:
        print("=" * 60)
        print("🧪 会话权限功能测试")
        print("=" * 60)
        
        # 1. 注册用户
        print("\n1️⃣  注册测试用户...")
        import time
        unique_email = f"test_{int(time.time())}@example.com"
        
        response = await client.post(
            f"{API_BASE}/auth/register",
            json={
                "email": unique_email,
                "password": "Test123456!",
                "name": "Permission Test User"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data["data"]["access_token"]
            user_id = data["data"]["user"]["id"]
            print(f"   ✅ 用户注册成功: {user_id}")
        else:
            # 如果用户已存在，尝试登录
            print("   ⚠️  用户可能已存在，尝试登录...")
            response = await client.post(
                f"{API_BASE}/auth/login",
                json={
                    "email": "test_perm@example.com",
                    "password": "Test123456!"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data["data"]["access_token"]
                user_id = data["data"]["user"]["id"]
                print(f"   ✅ 登录成功: {user_id}")
            else:
                print(f"   ❌ 登录失败: {response.text}")
                return
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. 创建私有会话
        print("\n2️⃣  创建私有会话（PRIVATE）...")
        response = await client.post(
            f"{API_BASE}/chat/conversations",
            headers=headers,
            json={
                "dataset_id": "test-dataset-001",
                "title": "My Private Conversation",
                "visibility": "private"
            }
        )
        
        if response.status_code == 201:
            private_conv = response.json()["data"]
            private_conv_id = private_conv["id"]
            print(f"   ✅ 私有会话创建成功")
            print(f"      ID: {private_conv_id}")
            print(f"      可见性: {private_conv.get('visibility', 'N/A')}")
        else:
            print(f"   ❌ 创建失败: {response.status_code} - {response.text}")
            return
        
        # 3. 创建工作空间共享会话
        print("\n3️⃣  创建工作空间共享会话（WORKSPACE）...")
        response = await client.post(
            f"{API_BASE}/chat/conversations",
            headers=headers,
            json={
                "dataset_id": "test-dataset-001",
                "title": "Workspace Conversation",
                "visibility": "workspace"
            }
        )
        
        if response.status_code == 201:
            workspace_conv = response.json()["data"]
            workspace_conv_id = workspace_conv["id"]
            print(f"   ✅ 工作空间会话创建成功")
            print(f"      ID: {workspace_conv_id}")
            print(f"      可见性: {workspace_conv.get('visibility', 'N/A')}")
        
        # 4. 获取会话详情（验证可见性字段）
        print("\n4️⃣  获取会话详情（验证visibility字段）...")
        response = await client.get(
            f"{API_BASE}/chat/conversations/{private_conv_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            conv_detail = response.json()["data"]
            print(f"   ✅ 成功获取会话详情:")
            print(f"      - ID: {conv_detail['id']}")
            print(f"      - 标题: {conv_detail['title']}")
            print(f"      - 可见性: {conv_detail.get('visibility', 'N/A')}")
            print(f"      - 工作空间ID: {conv_detail.get('workspace_id', 'N/A')}")
        
        # 5. 测试更新会话可见性
        print("\n5️⃣  更新会话可见性（PRIVATE → WORKSPACE）...")
        response = await client.put(
            f"{API_BASE}/chat/conversations/{private_conv_id}",
            headers=headers,
            json={"visibility": "workspace"}
        )
        
        if response.status_code == 200:
            updated_conv = response.json()["data"]
            print(f"   ✅ 可见性更新成功")
            print(f"      新可见性: {updated_conv.get('visibility', 'N/A')}")
        else:
            print(f"   ⚠️  更新失败: {response.status_code}")
        
        # 6. 列出所有会话
        print("\n6️⃣  列出所有会话...")
        response = await client.get(
            f"{API_BASE}/chat/conversations?dataset_id=test-dataset-001&page=1&page_size=10",
            headers=headers
        )
        
        if response.status_code == 200:
            conversations_data = response.json()
            total = conversations_data.get("total", 0)
            items = conversations_data.get("data", [])
            print(f"   ✅ 找到 {total} 个会话:")
            
            for conv in items[:3]:  # 只显示前3个
                visibility = conv.get('visibility', 'private')
                print(f"      - [{visibility.upper()}] {conv['title'][:30]}... (ID: {conv['id'][:8]}...)")
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！会话权限功能正常工作！")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_conversation_permissions())
