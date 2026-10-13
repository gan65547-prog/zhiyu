#!/usr/bin/env python3
"""测试DeepSeek API连接"""

import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

async def test_deepseek_api():
    """测试DeepSeek API连接"""
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("OPENAI_MODEL", "deepseek-chat")
    
    print(f"API Key: {api_key[:20]}..." if api_key else "API Key: 未设置")
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    print()
    
    if not api_key:
        print("❌ 错误：未设置 OPENAI_API_KEY")
        return False
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 测试聊天API
    print("🔄 测试 DeepSeek Chat API...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/v1/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是一个 helpful assistant."},
                        {"role": "user", "content": "你好，请用一句话介绍自己。"}
                    ],
                    "max_tokens": 100
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"✅ Chat API 测试成功！")
                print(f"📝 响应: {content[:100]}...")
                return True
            else:
                print(f"❌ Chat API 错误: {response.status_code}")
                print(f"响应: {response.text}")
                return False
    except Exception as e:
        print(f"❌ Chat API 异常: {e}")
        return False

async def test_deepseek_embedding():
    """测试DeepSeek Embedding API"""
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    
    if not api_key:
        return False
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("\n🔄 测试 DeepSeek Embedding API...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/v1/embeddings",
                headers=headers,
                json={
                    "model": "deepseek-embedding",
                    "input": "这是一个测试文本",
                    "encoding_format": "float"
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                embedding = result["data"][0]["embedding"]
                print(f"✅ Embedding API 测试成功！")
                print(f"📊 向量维度: {len(embedding)}")
                print(f"📊 向量前5个值: {embedding[:5]}")
                return True
            else:
                print(f"❌ Embedding API 错误: {response.status_code}")
                print(f"响应: {response.text}")
                return False
    except Exception as e:
        print(f"❌ Embedding API 异常: {e}")
        return False

async def main():
    print("=" * 50)
    print("DeepSeek API 连接测试")
    print("=" * 50)
    print()
    
    chat_ok = await test_deepseek_api()
    embedding_ok = await test_deepseek_embedding()
    
    print("\n" + "=" * 50)
    if chat_ok and embedding_ok:
        print("✅ 所有测试通过！DeepSeek API 配置正确。")
    else:
        print("❌ 部分测试失败，请检查配置。")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())
