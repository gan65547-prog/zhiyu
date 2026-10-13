#!/usr/bin/env python3
"""预生产环境核心业务流程验证（支持CSRF + Cookie持久化）"""

import asyncio
import os
import sys
from datetime import datetime

import httpx

BASE = os.environ.get("API_BASE", "http://localhost:8000").rstrip("/")
API = f"{BASE}/api/v1"


def _ok(name: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    extra = f" - {detail}" if detail else ""
    print(f"[{mark}] {name}{extra}")
    return cond


async def main() -> int:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    marker = f"CORE_FLOW_MARKER_{ts}"
    md_body = f"""# 核心流程验证文档

## 专有段落

本段包含唯一检索标记：{marker}。

RAG（Retrieval-Augmented Generation）将检索与生成结合，用于企业知识问答。
"""

    timeout = httpx.Timeout(180.0, connect=30.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r_live = await client.get(f"{BASE}/health/live")
        if not _ok("GET /health/live", r_live.status_code == 200, r_live.text[:120]):
            return 1

        r_ready = await client.get(f"{BASE}/health/ready")
        if not _ok("GET /health/ready", r_ready.status_code == 200, r_ready.text[:200]):
            return 1

        # Health endpoints are CSRF-exempt, so they do not issue the
        # double-submit token. Fetch a normal safe API resource first, just as
        # the browser does before its first mutating request.
        r_csrf = await client.get(f"{API}/datasets/")
        csrf_token = r_csrf.headers.get("x-csrf-token") or r_csrf.headers.get("X-CSRF-Token")
        csrf_cookie = client.cookies.get("csrf_token") or r_csrf.cookies.get("csrf_token")

        headers_a = {}
        if csrf_token:
            headers_a["X-CSRF-Token"] = csrf_token
        if csrf_cookie:
            client.cookies.set("csrf_token", csrf_cookie)

        email_a = f"flow_a_{ts}@example.com"
        reg_a = await client.post(
            f"{API}/auth/register",
            json={
                "email": email_a,
                "password": "Test123456!",
                "name": f"FlowA_{ts}",
            },
            headers=headers_a,
        )
        if not _ok("注册用户 A", reg_a.status_code == 201, reg_a.text[:300]):
            print(f"      Response headers: {dict(reg_a.headers)}")
            return 1
        data_a = reg_a.json().get("data") or {}
        token_a = data_a.get("access_token")
        user_a = data_a.get("user") or {}
        tenant_a = user_a.get("tenant_id")
        headers_a = {"Authorization": f"Bearer {token_a}"}
        if csrf_token:
            headers_a["X-CSRF-Token"] = csrf_token

        ds = await client.post(
            f"{API}/datasets/",
            headers=headers_a,
            json={
                "name": f"核心流程数据集_{ts}",
                "description": "remote verify",
            },
        )
        if not _ok("创建数据集", ds.status_code in (200, 201), ds.text[:400]):
            return 1
        ds_json = ds.json()
        dataset_id = (ds_json.get("data") or {}).get("id") or ds_json.get("id")
        if not dataset_id:
            print("FAIL: 无法解析 dataset_id", ds_json)
            return 1
        print(f"      dataset_id={dataset_id}")

        files = {
            "file": (f"verify_{ts}.md", md_body.encode("utf-8"), "text/markdown"),
        }
        up = await client.post(
            f"{API}/documents/datasets/{dataset_id}",
            headers=headers_a,
            files=files,
        )
        if not _ok("上传文档", up.status_code in (200, 201), up.text[:400]):
            return 1
        up_data = (up.json().get("data") or {})
        doc_id = up_data.get("id")
        print(f"      document_id={doc_id}")

        completed = False
        last_status = None
        for _ in range(60):
            try:
                lst = await client.get(
                    f"{API}/documents/datasets/{dataset_id}",
                    headers=headers_a,
                    params={"page": 1, "page_size": 10},
                )
            except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError):
                await asyncio.sleep(2)
                continue
            if lst.status_code != 200:
                await asyncio.sleep(2)
                continue
            items = (lst.json().get("data") or {}).get("items") or []
            for it in items:
                if str(it.get("id")) == str(doc_id):
                    last_status = it.get("status")
                    if last_status == "completed":
                        completed = True
                    break
            if completed:
                break
            await asyncio.sleep(2)

        if not _ok("文档索引完成 (status=completed)", completed, f"last_status={last_status}"):
            return 1

        chat_body = {
            "dataset_id": str(dataset_id),
            "query": f"{marker} 在文档中如何描述？请用一句话回答。",
            "retrieval_mode": "hybrid",
            "top_k": 5,
        }
        chat_r = await client.post(f"{API}/chat/", headers=headers_a, json=chat_body)
        if not _ok("RAG 对话 HTTP", chat_r.status_code == 200, chat_r.text[:500]):
            return 1
        chat_payload = chat_r.json().get("data") or {}
        answer = (chat_payload.get("answer") or "") + str(
            chat_payload.get("sources")
            or chat_payload.get("retrieved_documents")
            or ""
        )
        rag_hit = marker in answer or (
            "文档中没有" not in (chat_payload.get("answer") or "")
            and len(
                chat_payload.get("sources")
                or chat_payload.get("retrieved_documents")
                or []
            )
            > 0
        )
        _ok(
            "RAG 命中（标记出现在回答/来源，或有非空 sources）",
            rag_hit,
            f"answer_snip={(chat_payload.get('answer') or '')[:160]}",
        )

        conv = await client.post(
            f"{API}/chat/conversations",
            headers=headers_a,
            json={
                "dataset_id": str(dataset_id),
                "title": "隔离测试会话",
                "visibility": "private",
            },
        )
        if not _ok("创建 private 会话", conv.status_code == 201, conv.text[:300]):
            return 1
        conv_id = (conv.json().get("data") or {}).get("id")
        if not conv_id:
            print("FAIL: conversation id", conv.json())
            return 1

        email_b = f"flow_b_{ts}@example.com"
        reg_b = await client.post(
            f"{API}/auth/register",
            json={
                "email": email_b,
                "password": "Test123456!",
                "name": f"FlowB_{ts}",
            },
            headers=headers_a,
        )
        if not _ok("注册用户 B（另一租户）", reg_b.status_code == 201, reg_b.text[:200]):
            return 1
        data_b = reg_b.json().get("data") or {}
        token_b = data_b.get("access_token")
        headers_b = {"Authorization": f"Bearer {token_b}"}
        if csrf_token:
            headers_b["X-CSRF-Token"] = csrf_token
        tenant_b = (data_b.get("user") or {}).get("tenant_id")
        _ok("租户 A/B 不同", tenant_a != tenant_b, f"A={tenant_a} B={tenant_b}")

        cross = await client.get(
            f"{API}/chat/conversations/{conv_id}",
            headers=headers_b,
        )
        _ok(
            "跨租户访问他人会话 -> 404",
            cross.status_code == 404,
            str(cross.status_code),
        )

        cross_chat = await client.post(
            f"{API}/chat/",
            headers=headers_b,
            json={
                "dataset_id": str(dataset_id),
                "query": "test",
                "retrieval_mode": "hybrid",
                "top_k": 3,
            },
        )
        _ok(
            "跨租户使用他人 dataset 对话 -> 4xx",
            cross_chat.status_code in (400, 403, 404),
            f"code={cross_chat.status_code} body={cross_chat.text[:200]}",
        )

    print("\n=== 验证结束 ===")
    return 0 if completed and rag_hit else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
