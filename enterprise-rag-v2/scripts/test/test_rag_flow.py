#!/usr/bin/env python3
"""
RAG问答系统完整流程测试
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

def test_rag_flow():
    print("=" * 60)
    print("RAG问答系统完整流程测试")
    print("=" * 60)
    
    # 1. 登录
    print("\n[1] 登录...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "test@example.com",
        "password": "Test1234"
    })
    if resp.status_code != 200:
        print(f"❌ 登录失败: {resp.text}")
        return
    
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✅ 登录成功!")
    
    # 2. 创建工作空间
    print("\n[2] 创建工作空间...")
    resp = requests.post(f"{BASE_URL}/workspaces/", 
        headers=headers,
        json={"name": "RAG测试工作空间", "description": "测试问答功能"}
    )
    if resp.status_code not in [200, 201]:
        print(f"❌ 创建工作空间失败: {resp.text}")
        return
    
    workspace_id = resp.json()["data"]["id"]
    print(f"✅ 工作空间创建成功: {workspace_id}")
    
    # 3. 创建数据集
    print("\n[3] 创建数据集...")
    resp = requests.post(f"{BASE_URL}/datasets/",
        headers=headers,
        json={
            "name": "RAG测试数据集",
            "description": "用于测试RAG问答",
            "workspace_id": workspace_id
        }
    )
    if resp.status_code not in [200, 201]:
        print(f"❌ 创建数据集失败: {resp.text}")
        return
    
    dataset_id = resp.json()["data"]["id"]
    print(f"✅ 数据集创建成功: {dataset_id}")
    
    # 4. 上传文档
    print("\n[4] 上传文档...")
    test_content = """
    RAG（Retrieval-Augmented Generation，检索增强生成）是一种结合信息检索和文本生成的AI技术。
    
    RAG的工作原理：
    1. 检索阶段：从知识库中检索与用户问题相关的文档片段
    2. 增强阶段：将检索到的内容作为上下文
    3. 生成阶段：使用大语言模型基于上下文生成回答
    
    RAG的优势：
    - 减少幻觉：基于真实文档生成回答
    - 知识更新：无需重新训练模型即可更新知识
    - 可解释性：可以追溯回答的来源
    
    应用场景：
    - 企业知识库问答
    - 智能客服
    - 文档摘要
    """
    
    files = {"file": ("rag_intro.txt", test_content.encode("utf-8"), "text/plain")}
    resp = requests.post(f"{BASE_URL}/documents/datasets/{dataset_id}",
        headers=headers,
        files=files
    )
    if resp.status_code not in [200, 201]:
        print(f"❌ 上传文档失败: {resp.text}")
        return
    
    print(f"✅ 文档上传成功")
    
    # 5. 检查文档处理状态
    print("\n[5] 检查文档处理状态...")
    time.sleep(2)  # 等待处理
    
    resp = requests.get(f"{BASE_URL}/documents/datasets/{dataset_id}",
        headers=headers
    )
    if resp.status_code == 200:
        docs = resp.json().get("data", {}).get("items", [])
        for doc in docs:
            print(f"   文档: {doc.get('file_name')}, 状态: {doc.get('status')}, 分段数: {doc.get('chunk_count')}")
    
    # 6. 测试问答
    print("\n[6] 测试问答...")
    questions = [
        "什么是RAG技术？",
        "RAG有什么优势？",
        "RAG的工作原理是什么？"
    ]
    
    for question in questions:
        print(f"\n   问题: {question}")
        resp = requests.post(f"{BASE_URL}/chat/",
            headers=headers,
            json={
                "dataset_id": dataset_id,
                "query": question
            }
        )
        
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            answer = data.get("answer", "")
            docs = data.get("retrieved_documents", [])
            
            print(f"   ✅ 回答: {answer[:200]}...")
            print(f"   📚 检索到 {len(docs)} 个文档片段")
            
            if docs:
                for i, doc in enumerate(docs[:2]):
                    print(f"      [{i+1}] 相似度: {doc.get('score', 0):.3f}, 内容: {doc.get('content', '')[:100]}...")
        else:
            print(f"   ❌ 问答失败: {resp.text}")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    test_rag_flow()
