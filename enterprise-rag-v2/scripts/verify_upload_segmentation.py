#!/usr/bin/env python3
"""
验证：上传后后台 process_document 能读到新文档并完成分段（不再出现「文档不存在」竞态）。

用法（在 enterprise-rag-v2 目录下）:
  python3 scripts/verify_upload_segmentation.py
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time

# 以项目根为工作目录，便于 main / 配置 / DB 路径一致
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    db_path = os.path.join(_ROOT, "enterprise_rag.db")
    if not os.path.isfile(db_path):
        print("SKIP: 未找到 enterprise_rag.db，请先在本机跑过后端或初始化库")
        return 2

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id FROM datasets LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if not row:
        print("SKIP: 库中无数据集，请先创建数据集")
        return 2
    dataset_id = row[0]
    print(f"使用 dataset_id={dataset_id}")

    from fastapi.testclient import TestClient

    from main import app

    content = ("分段验证测试内容。" * 300).encode("utf-8")
    client = TestClient(app)
    resp = client.post(
        f"/api/v1/documents/datasets/{dataset_id}",
        files={"file": ("verify_seg_fix.txt", content, "text/plain")},
    )
    print(f"POST /documents/datasets/{{id}} -> {resp.status_code}")
    if resp.status_code != 201:
        print(resp.text[:2000])
        return 1
    body = resp.json()
    if not body.get("success"):
        print("响应 success=false:", body)
        return 1
    doc_id = (body.get("data") or {}).get("id")
    if not doc_id:
        print("响应中无 data.id:", body)
        return 1
    print(f"新建 document_id={doc_id}")

    # TestClient 会在收到响应后执行 BackgroundTasks
    deadline = time.time() + 120
    last = None
    while time.time() < deadline:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT lower(status), chunk_count FROM documents WHERE id = ?",
            (doc_id,),
        )
        last = cur.fetchone()
        cur.execute(
            "SELECT COUNT(*) FROM document_chunks WHERE document_id = ?",
            (doc_id,),
        )
        n_chunks = cur.fetchone()[0]
        conn.close()

        if last:
            st, cc = last[0], last[1]
            if st == "completed" and cc > 0 and n_chunks > 0:
                print(
                    f"通过: status=completed chunk_count={cc} document_chunks={n_chunks}"
                )
                return 0
            if st == "failed":
                print(f"失败: status=failed chunk_count={cc} document_chunks={n_chunks}")
                return 1
        time.sleep(0.3)

    print(f"超时: 最后状态 last={last}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
