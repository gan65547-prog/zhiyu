#!/usr/bin/env python3
"""调试聊天功能"""

import asyncio
from infrastructure.database.session import AsyncSessionLocal
from services.impl.chat_service import ChatServiceImpl
from uuid import UUID

async def debug_chat():
    """调试聊天功能"""
    async with AsyncSessionLocal() as session:
        chat_service = ChatServiceImpl(session)
        
        try:
            # 测试创建会话
            print("测试创建会话...")
            conv = await chat_service.create_conversation(
                dataset_id=UUID("0e004273-2bf8-4f9d-8139-d80791a2f718"),
                title="测试会话"
            )
            print(f"创建会话成功: {conv['id']}")
            
            # 测试聊天
            print("\n测试聊天...")
            result = await chat_service.chat(
                dataset_id=UUID("0e004273-2bf8-4f9d-8139-d80791a2f718"),
                query="你好，测试聊天功能",
                retrieval_mode="semantic",
                top_k=3,
                temperature=0.7,
                max_tokens=500
            )
            print(f"聊天成功: {result['answer']}")
            
        except Exception as e:
            print(f"错误: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_chat())
