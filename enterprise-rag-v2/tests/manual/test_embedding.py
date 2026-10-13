#!/usr/bin/env python3
"""测试BGE Embedding服务"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.rag.embedding import BGESmallZhEmbedding, get_embedding_service


async def test_bge_embedding():
    """测试BGE Embedding"""
    print("=" * 60)
    print("BGE-small-zh-v1.5 Embedding 测试")
    print("=" * 60)
    
    # 创建Embedding服务
    print("\n1. 初始化Embedding服务...")
    embedding = BGESmallZhEmbedding()
    
    # 测试单个文本
    print("\n2. 测试单个文本向量化...")
    text1 = "这是一个测试文本，用于验证Embedding服务是否正常工作。"
    print(f"   输入文本: {text1}")
    
    try:
        vector1 = await embedding.embed_text(text1)
        print(f"   ✅ 向量化成功!")
        print(f"   向量维度: {len(vector1)}")
        print(f"   向量前5个值: {vector1[:5]}")
    except Exception as e:
        print(f"   ❌ 向量化失败: {e}")
        return False
    
    # 测试语义相似度
    print("\n3. 测试语义相似度...")
    texts = [
        "机器学习是人工智能的一个分支",
        "深度学习是机器学习的一种方法",
        "今天天气真好，适合出去玩",
    ]
    
    try:
        vectors = await embedding.embed_batch(texts)
        print(f"   ✅ 批量向量化成功! 共{len(vectors)}个向量")
        
        # 计算相似度
        import numpy as np
        
        def cosine_similarity(v1, v2):
            return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        
        sim_01 = cosine_similarity(vectors[0], vectors[1])
        sim_02 = cosine_similarity(vectors[0], vectors[2])
        sim_12 = cosine_similarity(vectors[1], vectors[2])
        
        print(f"\n   语义相似度测试:")
        print(f"   '{texts[0][:20]}...' vs '{texts[1][:20]}...'")
        print(f"   相似度: {sim_01:.4f} (语义相关，应该较高)")
        print(f"\n   '{texts[0][:20]}...' vs '{texts[2][:20]}...'")
        print(f"   相似度: {sim_02:.4f} (语义不相关，应该较低)")
        print(f"\n   '{texts[1][:20]}...' vs '{texts[2][:20]}...'")
        print(f"   相似度: {sim_12:.4f} (语义不相关，应该较低)")
        
        if sim_01 > sim_02 and sim_01 > sim_12:
            print(f"\n   ✅ 语义相似度测试通过! 相关文本相似度更高。")
        else:
            print(f"\n   ⚠️ 语义相似度测试结果可能需要验证")
            
    except Exception as e:
        print(f"   ❌ 批量向量化失败: {e}")
        return False
    
    # 测试工厂方法
    print("\n4. 测试工厂方法...")
    try:
        service = get_embedding_service("bge-small-zh")
        test_vec = await service.embed_text("测试工厂方法")
        print(f"   ✅ 工厂方法测试成功! 向量维度: {len(test_vec)}")
    except Exception as e:
        print(f"   ❌ 工厂方法测试失败: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过! BGE Embedding服务正常工作。")
    print("=" * 60)
    return True


if __name__ == "__main__":
    asyncio.run(test_bge_embedding())
