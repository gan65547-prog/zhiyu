#!/usr/bin/env python3
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_qa_flow():
    print("=" * 50)
    print("测试问答核心业务流程")
    print("=" * 50)
    
    # 1. 登录
    print("\n[1] 登录...")
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "test@example.com",
        "password": "Test1234"
    })
    print(f"状态码: {resp.status_code}")
    if resp.status_code != 200:
        print(f"错误: {resp.text}")
        return
    
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("登录成功!")
    
    # 2. 创建工作空间
    print("\n[2] 创建工作空间...")
    resp = requests.post(f"{BASE_URL}/workspaces/", 
        headers=headers,
        json={"name": "测试工作空间", "description": "用于测试问答功能"}
    )
    print(f"状态码: {resp.status_code}")
    if resp.status_code not in [200, 201]:
        print(f"错误: {resp.text}")
        return
    
    ws_data = resp.json()
    print(f"工作空间创建成功: {ws_data}")
    workspace_id = ws_data["data"]["id"]
    
    # 3. 创建数据集
    print("\n[3] 创建数据集...")
    resp = requests.post(f"{BASE_URL}/datasets/",
        headers=headers,
        json={
            "name": "测试数据集",
            "description": "用于测试问答",
            "workspace_id": workspace_id
        }
    )
    print(f"状态码: {resp.status_code}")
    if resp.status_code not in [200, 201]:
        print(f"错误: {resp.text}")
        return
    
    ds_data = resp.json()
    print(f"数据集创建成功: {ds_data}")
    dataset_id = ds_data["data"]["id"]
    
    # 4. 上传文档
    print("\n[4] 上传文档...")
    test_content = """
    企业RAG系统介绍
    
    RAG（Retrieval-Augmented Generation）是一种结合检索和生成的AI技术。
    它首先从知识库中检索相关文档，然后利用大语言模型生成回答。
    
    主要特点：
    1. 支持多租户架构
    2. 支持向量检索和关键词检索
    3. 支持多种文档格式
    4. 支持流式输出
    
    使用方法：
    用户上传文档后，系统会自动进行分块和向量化处理。
    然后用户可以进行问答，系统会检索相关内容并生成回答。
    """
    
    files = {"file": ("test.txt", test_content.encode(), "text/plain")}
    resp = requests.post(f"{BASE_URL}/documents/datasets/{dataset_id}",
        headers=headers,
        files=files
    )
    print(f"状态码: {resp.status_code}")
    if resp.status_code not in [200, 201]:
        print(f"错误: {resp.text}")
    else:
        doc_data = resp.json()
        print(f"文档上传成功: {doc_data}")
    
    # 5. 测试问答
    print("\n[5] 测试问答...")
    resp = requests.post(f"{BASE_URL}/chat/",
        headers=headers,
        json={
            "dataset_id": dataset_id,
            "query": "什么是RAG技术？"
        }
    )
    print(f"状态码: {resp.status_code}")
    if resp.status_code != 200:
        print(f"错误: {resp.text}")
    else:
        chat_data = resp.json()
        print(f"问答结果: {json.dumps(chat_data, ensure_ascii=False, indent=2)}")
    
    print("\n" + "=" * 50)
    print("测试完成!")
    print("=" * 50)

if __name__ == "__main__":
    test_qa_flow()
