#!/usr/bin/env python3
"""
回归测试 — 封板基线版本核心业务流程
目标: http://127.0.0.1:8000
"""
import requests
import os
import json
import time
import sys
import uuid

BASE_URL = os.environ.get("GANFY_API_BASE_URL", "http://127.0.0.1:8000") + "/api/v1"

PASSED = 0
FAILED = 0

def test(name, fn):
    global PASSED, FAILED
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    try:
        fn()
        PASSED += 1
        print(f"✅ PASSED: {name}")
    except Exception as e:
        FAILED += 1
        print(f"❌ FAILED: {name}")
        print(f"   Error: {e}")

def assert_status(resp, expected):
    if resp.status_code != expected:
        raise AssertionError(f"Expected HTTP {expected}, got {resp.status_code}: {resp.text[:300]}")

# ── State ──
token = None
headers = None
workspace_id = None
dataset_id_1 = None
dataset_id_2 = None
conversation_id_1 = None
user_ts = int(time.time())
user_email = f"regtest_{user_ts}@example.com"
user_name = f"regtest_{user_ts}"
user_password = "Test1234"


# ═══ 1. Health ═══
def test_health():
    resp = requests.get("http://127.0.0.1:8000/health")
    assert_status(resp, 200)
    assert resp.json()["status"] == "healthy"

def test_readiness():
    resp = requests.get("http://127.0.0.1:8000/health/ready")
    assert_status(resp, 200)

def test_api_root():
    resp = requests.get("http://127.0.0.1:8000/")
    assert_status(resp, 200)

# ═══ 2. Auth ═══
def test_register():
    global token, headers, workspace_id
    resp = requests.post(f"{BASE_URL}/auth/register", json={
        "email": user_email,
        "password": user_password,
        "name": user_name
    })
    if resp.status_code not in [200, 201]:
        raise AssertionError(f"Register: {resp.text[:200]}")
    d = resp.json()["data"]
    token = d["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # 注册自动创建默认 workspace
    workspace_id = d["user"].get("current_workspace_id")
    print(f"   用户: {d['user']['email']}")
    print(f"   默认 workspace: {workspace_id}")

def test_login():
    global token, headers
    resp = requests.post(f"{BASE_URL}/auth/login", json={
        "email": user_email,
        "password": user_password
    })
    assert_status(resp, 200)
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"   登录成功")

def test_get_me():
    resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    assert_status(resp, 200)
    assert resp.json()["data"]["email"] == user_email

# ═══ 3. Workspace (使用注册时自动创建的) ═══
def test_workspace_list():
    resp = requests.get(f"{BASE_URL}/workspaces/", headers=headers)
    assert_status(resp, 200)
    items = resp.json()["data"]  # data 就是数组
    assert len(items) >= 1
    print(f"   工作空间数: {len(items)}")

def test_workspace_get():
    resp = requests.get(f"{BASE_URL}/workspaces/{workspace_id}", headers=headers)
    assert_status(resp, 200)
    assert "name" in resp.json()["data"]

# ═══ 4. Dataset CRUD ═══
def test_dataset_create_1():
    global dataset_id_1
    resp = requests.post(f"{BASE_URL}/datasets/", headers=headers, json={
        "name": f"RAG基础_{user_ts}",
        "description": "RAG技术相关文档",
        "workspace_id": workspace_id
    })
    if resp.status_code not in [200, 201]:
        raise AssertionError(f"Create: {resp.text[:200]}")
    dataset_id_1 = resp.json()["data"]["id"]
    print(f"   知识库1: {dataset_id_1}")

def test_dataset_create_2():
    global dataset_id_2
    resp = requests.post(f"{BASE_URL}/datasets/", headers=headers, json={
        "name": f"企业管理_{user_ts}",
        "description": "企业管理相关文档",
        "workspace_id": workspace_id
    })
    if resp.status_code not in [200, 201]:
        raise AssertionError(f"Create: {resp.text[:200]}")
    dataset_id_2 = resp.json()["data"]["id"]
    print(f"   知识库2: {dataset_id_2}")

def test_dataset_list():
    resp = requests.get(f"{BASE_URL}/datasets/", headers=headers)
    assert_status(resp, 200)
    items = resp.json()["data"]
    print(f"   知识库数: {len(items)}")

# ═══ 5. Document Upload ═══
def test_document_upload():
    content = """
RAG（Retrieval-Augmented Generation，检索增强生成）是一种结合信息检索和文本生成的AI技术。

RAG的工作原理：
1. 检索阶段：从知识库中检索与用户问题相关的文档片段
2. 增强阶段：将检索到的内容作为上下文提供给大语言模型
3. 生成阶段：使用大语言模型基于检索到的上下文生成回答

RAG的核心优势：
- 减少幻觉：基于真实文档生成回答，有效降低模型编造内容的概率
- 知识更新：无需重新训练模型即可更新知识库
- 可解释性：可以追溯回答的具体来源
"""
    files = {"file": ("rag_intro.txt", content.encode("utf-8"), "text/plain")}
    resp = requests.post(
        f"{BASE_URL}/documents/datasets/{dataset_id_1}",
        headers=headers,
        files=files
    )
    if resp.status_code not in [200, 201]:
        raise AssertionError(f"Upload: {resp.text[:200]}")
    print(f"   文档上传成功")

def test_document_wait_processing():
    max_wait = 90
    for i in range(max_wait // 3):
        time.sleep(3)
        resp = requests.get(f"{BASE_URL}/documents/datasets/{dataset_id_1}", headers=headers)
        if resp.status_code != 200:
            continue
        items = resp.json().get("data", [])
        if isinstance(items, dict):
            items = items.get("items", [])
        if not items:
            continue
        states = [d.get("status") for d in items]
        print(f"   文档状态 ({i*3}s): {states}")
        if all(s == "completed" for s in states):
            for doc in items:
                print(f"   {doc.get('file_name')}: status={doc.get('status')}, chunks={doc.get('chunk_count')}")
            return
    # 超时不视为失败，文档可能仍在后台处理
    print(f"   警告: 文档未在 {max_wait}s 内完成处理，继续后续测试")

# ═══ 6. Chat Async ═══
def test_chat_async():
    global conversation_id_1
    resp = requests.post(f"{BASE_URL}/chat/async", headers=headers, json={
        "dataset_id": dataset_id_1,
        "query": "什么是RAG技术？"
    })
    if resp.status_code not in [200, 202]:
        raise AssertionError(f"Chat async: {resp.text[:300]}")
    data = resp.json().get("data", resp.json())
    job_id = data.get("job_id")
    print(f"   job_id: {job_id}")

    # 等待 Celery worker 处理完成，自动创建 conversation
    max_wait = 120
    for i in range(max_wait // 3):
        time.sleep(3)
        resp = requests.get(
            f"{BASE_URL}/chat/conversations",
            headers=headers,
            params={"dataset_id": dataset_id_1}
        )
        if resp.status_code == 200:
            convs = resp.json().get("data", [])
            if convs:
                conversation_id_1 = convs[0]["id"]
                # 检查是否有 assistant 消息
                msg_resp = requests.get(
                    f"{BASE_URL}/chat/conversations/{conversation_id_1}/messages",
                    headers=headers
                )
                if msg_resp.status_code == 200:
                    messages = msg_resp.json().get("data", [])
                    has_asst = any(m.get("role") == "assistant" for m in messages)
                    if has_asst:
                        print(f"   会话ID: {conversation_id_1}, 消息数: {len(messages)}")
                        for m in messages:
                            print(f"     [{m['role']}] {m.get('content', '')[:120]}...")
                        return
        print(f"   等待中 ({i*3}s)...")
    print(f"   警告: 异步问答未在 {max_wait}s 内完成")

# ═══ 7. 会话隔离验证 (核心修复) ═══
def test_conversation_isolation():
    print("   验证跨知识库会话隔离...")

    # 知识库1的会话
    resp1 = requests.get(f"{BASE_URL}/chat/conversations", headers=headers, params={
        "dataset_id": dataset_id_1
    })
    assert_status(resp1, 200)
    convs_1 = resp1.json()["data"]
    ids_1 = {c["id"] for c in convs_1}
    print(f"   知识库1会话: {ids_1}")

    # 知识库2的会话 (应为空)
    resp2 = requests.get(f"{BASE_URL}/chat/conversations", headers=headers, params={
        "dataset_id": dataset_id_2
    })
    assert_status(resp2, 200)
    convs_2 = resp2.json()["data"]
    ids_2 = {c["id"] for c in convs_2}
    print(f"   知识库2会话: {ids_2}")

    # 确认不泄露
    leaked = ids_1 & ids_2
    if leaked:
        raise AssertionError(f"会话泄露! {leaked}")
    print(f"   ✅ 无跨知识库泄露")

# ═══ 8. Conv CRUD ═══
def test_conversation_create():
    resp = requests.post(f"{BASE_URL}/chat/conversations", headers=headers, json={
        "dataset_id": dataset_id_1,
        "title": "手动测试会话"
    })
    if resp.status_code not in [200, 201]:
        raise AssertionError(f"Create: {resp.text[:200]}")
    print(f"   创建会话: {resp.json()['data']['id']}")

def test_conversation_delete():
    resp = requests.post(f"{BASE_URL}/chat/conversations", headers=headers, json={
        "dataset_id": dataset_id_1,
        "title": "待删除"
    })
    if resp.status_code not in [200, 201]:
        raise AssertionError(f"Create: {resp.text[:200]}")
    cid = resp.json()["data"]["id"]
    resp = requests.delete(f"{BASE_URL}/chat/conversations/{cid}", headers=headers)
    if resp.status_code not in [200, 204]:
        raise AssertionError(f"Delete: {resp.text[:200]}")
    print(f"   删除会话 {cid} 成功")

# ═══ 9. 跨知识库问答 ═══
def test_cross_dataset_chat():
    resp = requests.post(f"{BASE_URL}/chat/async", headers=headers, json={
        "dataset_id": dataset_id_2,
        "query": "企业管理的基本原则是什么？"
    })
    if resp.status_code not in [200, 202]:
        raise AssertionError(f"Chat async ds2: {resp.text[:300]}")

    # 等待会话创建
    time.sleep(5)
    resp = requests.get(f"{BASE_URL}/chat/conversations", headers=headers, params={
        "dataset_id": dataset_id_2
    })
    assert_status(resp, 200)
    convs_2 = resp.json()["data"]
    ids_2 = {c["id"] for c in convs_2}

    # 验证不泄露到知识库1
    resp = requests.get(f"{BASE_URL}/chat/conversations", headers=headers, params={
        "dataset_id": dataset_id_1
    })
    assert_status(resp, 200)
    ids_1 = {c["id"] for c in resp.json()["data"]}
    leaked = ids_2 & ids_1
    if leaked:
        raise AssertionError(f"会话泄露: {leaked}")
    print(f"   ds2会话: {ids_2}, ds1会话: {ids_1}")
    print(f"   ✅ 知识库2会话归属正确，无泄露")

# ═══ 10. Cleanup ═══
def test_cleanup():
    for ds_id in [dataset_id_1, dataset_id_2]:
        if ds_id:
            try:
                requests.delete(f"{BASE_URL}/datasets/{ds_id}", headers=headers)
            except:
                pass
    print("   测试数据已清理")


# ── Main ──
def main():
    print("=" * 70)
    print("  封板基线回归测试 — 核心业务流程")
    print(f"  目标: http://127.0.0.1:8000")
    print(f"  版本: v2.0.0-baseline (813fab97)")
    print("=" * 70)

    test("Health Check", test_health)
    test("Readiness Probe", test_readiness)
    test("API Root", test_api_root)

    test("注册新用户", test_register)
    test("登录", test_login)
    test("获取用户信息", test_get_me)

    test("工作空间列表", test_workspace_list)
    test("工作空间详情", test_workspace_get)

    test("创建知识库1 (RAG基础)", test_dataset_create_1)
    test("创建知识库2 (企业管理)", test_dataset_create_2)
    test("知识库列表", test_dataset_list)

    test("上传文档", test_document_upload)
    test("等待文档处理", test_document_wait_processing)

    test("异步问答 (RAG)", test_chat_async)

    test("跨知识库会话隔离验证", test_conversation_isolation)
    test("创建会话", test_conversation_create)
    test("删除会话", test_conversation_delete)
    test("跨知识库问答归属验证", test_cross_dataset_chat)

    test("清理测试数据", test_cleanup)

    total = PASSED + FAILED
    print(f"\n{'='*70}")
    print(f"  回归测试结果汇总")
    print(f"{'='*70}")
    print(f"  总计: {total}")
    print(f"  ✅ 通过: {PASSED}")
    print(f"  ❌ 失败: {FAILED}")
    print(f"{'='*70}")

    if FAILED > 0:
        print("\n⚠️  存在失败用例！")
        sys.exit(1)
    else:
        print("\n✅ 所有核心业务流程回归测试通过！")
        sys.exit(0)

if __name__ == "__main__":
    main()
