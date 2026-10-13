#!/usr/bin/env python3
"""
检索诊断脚本
一次性检查：Qdrant 状态、向量数据、dataset_id 对齐、embedding 模型
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("HF_HOME", os.path.join(os.path.dirname(__file__), ".cache/huggingface"))
os.environ.setdefault(
    "SENTENCE_TRANSFORMERS_HOME",
    os.path.join(os.path.dirname(__file__), ".cache/sentence_transformers")
)
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("EMBEDDING_DEVICE", "cpu")


async def main():
    print("=" * 60)
    print("RAG 检索诊断工具")
    print("=" * 60)

    # ── 1. 检查 Qdrant 服务 ───────────────────────────────────────
    print("\n[1] 检查 Qdrant 服务可访问性")
    try:
        import httpx
        from core.rag_config import get_rag_config
        config = get_rag_config()
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{config.qdrant_url}/collections")
        if r.status_code == 200:
            collections = r.json().get("result", {}).get("collections", [])
            print(f"  ✅ Qdrant 可访问: {config.qdrant_url}")
            print(f"  集合列表: {[c['name'] for c in collections]}")
            qdrant_ok = True
        else:
            print(f"  ❌ Qdrant 响应异常: {r.status_code}")
            qdrant_ok = False
    except Exception as e:
        print(f"  ❌ Qdrant 无法连接: {e}")
        qdrant_ok = False

    # ── 2. 检查 EmbeddedQdrant ────────────────────────────────────
    print("\n[2] 检查 EmbeddedQdrantStore (本地文件 Qdrant)")
    try:
        from qdrant_client import QdrantClient
        qdrant_data_path = os.path.join(os.path.dirname(__file__), "qdrant_data")
        if os.path.exists(qdrant_data_path):
            client = QdrantClient(path=qdrant_data_path)
            colls = client.get_collections()
            print(f"  ✅ EmbeddedQdrant 存在: {qdrant_data_path}")
            embedded_collections = [c.name for c in colls.collections]
            print(f"  集合列表: {embedded_collections}")
            for cname in embedded_collections:
                info = client.get_collection(cname)
                count = client.count(cname)
                print(f"  集合 {cname}: {count.count} 个向量, 维度={info.config.params.vectors.size}")
            embedded_ok = True
        else:
            print(f"  ⚠️  qdrant_data 目录不存在: {qdrant_data_path}")
            embedded_ok = False
    except Exception as e:
        print(f"  ❌ EmbeddedQdrant 错误: {e}")
        embedded_ok = False

    # ── 3. 检查数据库: datasets + documents ──────────────────────
    print("\n[3] 检查数据库中 datasets 和 documents")
    try:
        from infrastructure.database.session import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("""
                SELECT d.id, d.name, w.id as workspace_id, w.name as ws_name,
                       (SELECT COUNT(*) FROM documents doc WHERE doc.dataset_id = d.id AND doc.status = 'completed') as doc_count
                FROM datasets d
                JOIN workspaces w ON d.workspace_id = w.id
                LIMIT 20
            """))
            rows = result.fetchall()
            if rows:
                print(f"  ✅ 找到 {len(rows)} 个数据集:")
                for row in rows:
                    print(f"    dataset_id={row[0]}, name={row[1]}, workspace={row[3]}, "
                          f"completed_docs={row[4]}")
            else:
                print("  ❌ 数据库中没有数据集！")
    except Exception as e:
        print(f"  ❌ 数据库查询失败: {e}")

    # ── 4. 检查向量 payload 中的 dataset_id ──────────────────────
    print("\n[4] 检查 Qdrant 向量 payload 中的 dataset_id")
    if embedded_ok:
        try:
            from qdrant_client import QdrantClient
            qdrant_data_path = os.path.join(os.path.dirname(__file__), "qdrant_data")
            client = QdrantClient(path=qdrant_data_path)
            for cname in embedded_collections:
                points, _ = client.scroll(cname, limit=5, with_payload=True)
                print(f"  集合 {cname} 前5条向量的 payload:")
                for p in points:
                    payload = p.payload or {}
                    print(f"    id={str(p.id)[:8]}.. dataset_id={payload.get('dataset_id')} "
                          f"doc_name={payload.get('document_name')} "
                          f"content前50={payload.get('content','')[:50]}")
        except Exception as e:
            print(f"  ❌ 读取 payload 失败: {e}")
    elif qdrant_ok:
        try:
            import httpx
            from core.rag_config import get_rag_config
            cfg = get_rag_config()
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{cfg.qdrant_url}/collections/{cfg.collection_name}/points/scroll",
                    json={"limit": 5, "with_payload": True}
                )
                if r.status_code == 200:
                    pts = r.json().get("result", {}).get("points", [])
                    for p in pts:
                        payload = p.get("payload", {})
                        print(f"    dataset_id={payload.get('dataset_id')} "
                              f"doc_name={payload.get('document_name')} "
                              f"content前50={payload.get('content','')[:50]}")
        except Exception as e:
            print(f"  ❌ 远程 Qdrant scroll 失败: {e}")
    else:
        print("  ⚠️  Qdrant 不可用，跳过 payload 检查")

    # ── 5. 检查 embedding 模型 ────────────────────────────────────
    print("\n[5] 检查 Embedding 模型")
    try:
        from core.rag.embedding import get_embedding_service, DeepSeekEmbedding
        emb = get_embedding_service()
        print(f"  get_embedding_service() 返回: {type(emb).__name__}")
        vec = await emb.embed_text("测试文本")
        print(f"  ✅ 向量化成功, 维度={len(vec)}")
    except Exception as e:
        print(f"  ❌ Embedding 失败: {e}")

    # ── 6. 检查 RAGEngineImpl 使用的 embedding ────────────────────
    print("\n[6] 检查 RAGEngineImpl 默认 embedding 选择")
    try:
        from core.rag_config import get_rag_config
        cfg = get_rag_config()
        print(f"  deepseek_api_key 是否有值: {bool(cfg.deepseek_api_key)}")
        from core.rag.rag_engine import RAGEngineImpl
        engine = RAGEngineImpl()
        print(f"  RAGEngineImpl.embedding_service 类型: {type(engine.embedding_service).__name__}")
        print(f"  RAGEngineImpl.response_generator 类型: {type(engine.response_generator).__name__}")
    except Exception as e:
        print(f"  ❌ 检查 RAGEngineImpl 失败: {e}")

    # ── 7. 尝试做一次真实检索 ─────────────────────────────────────
    print("\n[7] 尝试一次真实向量检索（不经过 LLM）")
    try:
        from core.rag.embedding import get_embedding_service
        from core.rag.vector_store import create_vector_store
        from core.rag.collection_manager import CollectionManager
        from infrastructure.database.session import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as session:
            result = await session.execute(text(
                "SELECT d.id, w.id as workspace_id FROM datasets d "
                "JOIN workspaces w ON d.workspace_id = w.id LIMIT 1"
            ))
            row = result.first()
            if not row:
                print("  ❌ 数据库中没有任何数据集，无法检索")
            else:
                dataset_id = str(row[0])
                workspace_id = str(row[1])
                collection_name = CollectionManager.get_workspace_collection_name(workspace_id)
                print(f"  使用 dataset_id={dataset_id}, collection={collection_name}")

                embedding_svc = get_embedding_service()
                store = await create_vector_store(
                    collection_name=collection_name,
                    embedding_service=embedding_svc,
                    use_memory_fallback=True
                )
                print(f"  向量存储类型: {type(store).__name__}")

                query_vec = await embedding_svc.embed_text("投资")
                results = await store.search(
                    query_vector=query_vec,
                    top_k=5,
                    score_threshold=None,   # 关闭阈值过滤
                    filters=None            # 不过滤，看全局有没有数据
                )
                print(f"  无过滤搜索结果数: {len(results)}")

                results_filtered = await store.search(
                    query_vector=query_vec,
                    top_k=5,
                    score_threshold=None,
                    filters={"dataset_id": dataset_id}
                )
                print(f"  按 dataset_id 过滤搜索结果数: {len(results_filtered)}")

                if results:
                    print(f"  前1条结果 payload: {results[0].get('payload', {})}")
                else:
                    print("  ⚠️  向量存储为空 -> 文档未被向量化或向量数据丢失!")
    except Exception as e:
        import traceback
        print(f"  ❌ 检索测试失败: {e}")
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("诊断完成")


if __name__ == "__main__":
    asyncio.run(main())
