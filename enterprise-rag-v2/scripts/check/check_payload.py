import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from infrastructure.database.db import get_db
from infrastructure.database.models import Workspace
from core.rag.vector_store import create_vector_store
from core.rag.embedding_service import get_embedding_service

async def check_payload():
    """检查 Qdrant 中的 payload 结构"""
    
    # 先从数据库获取 workspace_id
    async for db in get_db():
        # 获取第一个 workspace
        result = await db.execute(select(Workspace).limit(1))
        workspace = result.scalar_one_or_none()
        if not workspace:
            print("没有找到 workspace")
            return
        
        workspace_id = workspace.id
        collection_name = f"documents_{workspace_id}"
        print(f"使用 collection: {collection_name}")
        
        # 获取 vector store
        embedding_service = get_embedding_service()
        vector_store = await create_vector_store(
            collection_name=collection_name,
            embedding_service=embedding_service
        )
        
        # 搜索一些点来查看 payload
        test_embedding = await embedding_service.embed_text("test")
        results = await vector_store.search(
            query_vector=test_embedding,
            top_k=3
        )
        
        print(f"\n找到 {len(results)} 个结果:")
        for i, r in enumerate(results):
            print(f"\n--- 结果 {i+1} ---")
            print(f"ID: {r.get('id')}")
            print(f"Score: {r.get('score')}")
            payload = r.get('payload', {})
            print(f"Payload keys: {list(payload.keys())}")
            print(f"Payload content: {payload}")
            
            # 查看 content 的前 100 字符
            if 'content' in payload:
                print(f"Content (前100字符): {payload['content'][:100]}...")

if __name__ == "__main__":
    asyncio.run(check_payload())
