"""
向量存储服务

提供Qdrant向量数据库的客户端封装
"""

import asyncio
from typing import List, Optional, Dict, Any
import httpx
import threading

from core.rag_config import get_rag_config
from core.rag.embedding import EmbeddingService
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class QdrantClientManager:
    """全局Qdrant客户端管理器 - 解决并发访问问题"""
    _instance = None
    _lock = threading.Lock()
    _client = None
    
    @classmethod
    def get_client(cls, storage_path: str = "./qdrant_data"):
        """获取全局Qdrant客户端单例"""
        if cls._client is None:
            with cls._lock:
                if cls._client is None:
                    from qdrant_client import QdrantClient
                    cls._client = QdrantClient(path=storage_path, check_compatibility=False)
        return cls._client
    
    @classmethod
    def reset(cls):
        """重置客户端（用于测试）"""
        with cls._lock:
            cls._client = None


class VectorStore:
    """向量存储服务"""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        embedding_service: Optional[EmbeddingService] = None
    ):
        self.config = get_rag_config()
        self.collection_name = collection_name or self.config.collection_name
        self.embedding_service = embedding_service or EmbeddingService()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端（直连 Qdrant，不走系统代理，避免 localhost 被代理成 502）"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0, trust_env=False)
        return self._client

    async def upsert(
        self,
        points: List[Dict[str, Any]],
        wait: bool = True
    ) -> bool:
        """插入或更新向量"""
        logger.info(f"开始 upsert {len(points)} 个向量到 collection: {self.collection_name}")

        url = f"{self.config.qdrant_url}/collections/{self.collection_name}/points"
        payload = {"points": points}
        params = {"wait": "true"} if wait else {}
        # Some Qdrant versions close an upsert request instead of returning
        # 404 when the collection has not been created yet. Check first so a
        # fresh workspace can self-heal before the first document is indexed.
        if points and not await self.collection_exists():
            stale_client = self._client
            self._client = None
            if stale_client:
                try:
                    await stale_client.aclose()
                except Exception:  # noqa: BLE001 - cleanup must not hide recovery
                    logger.debug("关闭 Qdrant 检查客户端失败", exc_info=True)
            vector_size = len(points[0].get("vector", []))
            if not vector_size or not await self.create_collection(vector_size=vector_size):
                logger.error("Qdrant collection 不存在且自动创建失败: %s", self.collection_name)
                return False
            logger.info("Qdrant collection 已预创建: %s", self.collection_name)
        # Qdrant may close a keep-alive connection while loading or compacting
        # a collection. Recreate the transport for transient network errors;
        # HTTP application errors remain non-retryable and are reported.
        for attempt in range(3):
            client = await self._get_client()
            try:
                response = await client.put(url, json=payload, params=params)
                logger.info(f"upsert 响应状态码: {response.status_code}")
                if response.status_code == 404:
                    vector_size = len(points[0].get("vector", [])) if points else None
                    if not vector_size or not await self.create_collection(vector_size=vector_size):
                        logger.error("Qdrant collection 不存在且自动创建失败: %s", self.collection_name)
                        return False
                    logger.info("Qdrant collection 已创建，重试 upsert: %s", self.collection_name)
                    continue
                if response.status_code != 200:
                    logger.error(f"upsert 失败，响应: {response.text}")
                return response.status_code == 200
            except httpx.TransportError as exc:
                logger.warning(
                    "Qdrant upsert 传输失败，将重建客户端重试 attempt=%s/3 error=%s",
                    attempt + 1,
                    exc,
                )
                if self._client is client:
                    self._client = None
                try:
                    await client.aclose()
                except Exception:  # noqa: BLE001 - cleanup must not hide retry
                    logger.debug("关闭失效 Qdrant 客户端失败", exc_info=True)
                if attempt < 2:
                    await asyncio.sleep(0.25 * (attempt + 1))
            except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
                logger.error(f"upsert 异常: {exc}", exc_info=True)
                return False
        return False

    async def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索"""
        logger.info(f"开始搜索，collection: {self.collection_name}, top_k: {top_k}, filters: {filters}")
        
        client = await self._get_client()

        try:
            query = {
                "vector": query_vector,
                "limit": top_k,
                "with_payload": True
            }

            if score_threshold:
                query["score_threshold"] = score_threshold

            if filters:
                query["filter"] = self._build_qdrant_filter(filters)

            response = await client.post(
                f"{self.config.qdrant_url}/collections/{self.collection_name}/points/search",
                json=query
            )

            logger.info(f"搜索响应状态码: {response.status_code}")
            if response.status_code == 200:
                results = response.json().get("result", [])
                logger.info(f"搜索到 {len(results)} 个结果")
                return [
                    {
                        "id": r["id"],
                        "score": r["score"],
                        "payload": r.get("payload", {})
                    }
                    for r in results
                ]
            else:
                logger.error(f"搜索失败，响应: {response.text}")
            return []
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"搜索异常: {e}", exc_info=True)
            return []

    def _build_qdrant_filter(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """将简化过滤条件转换为Qdrant REST filter格式。"""
        must_conditions: List[Dict[str, Any]] = []

        for key, value in filters.items():
            if isinstance(value, dict) and "$in" in value:
                must_conditions.append({
                    "key": key,
                    "match": {"any": value["$in"]}
                })
            else:
                must_conditions.append({
                    "key": key,
                    "match": {"value": value}
                })

        return {"must": must_conditions}

    async def semantic_search(
        self,
        query_text: str,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        workspace_id: Optional[str] = None,
        dataset_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """语义搜索"""
        query_vector = await self.embedding_service.embed_text(query_text)

        filters = {}
        if workspace_id:
            filters["workspace_id"] = workspace_id
        if dataset_id:
            filters["dataset_id"] = dataset_id

        return await self.search(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
            filters=filters if filters else None
        )

    async def delete(self, point_ids: List[str], wait: bool = True) -> bool:
        """删除向量"""
        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.config.qdrant_url}/collections/{self.collection_name}/points/delete",
                json={"points": point_ids},
                params={"wait": "true"} if wait else {}
            )
            return response.status_code == 200
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError):
            return False

    async def create_collection(self, vector_size: Optional[int] = None) -> bool:
        """创建集合"""
        client = await self._get_client()
        size = vector_size or self.config.vector_size

        try:
            response = await client.put(
                f"{self.config.qdrant_url}/collections/{self.collection_name}",
                json={
                    "vectors": {
                        "size": size,
                        "distance": "Cosine"
                    }
                }
            )
            if response.status_code in [200, 201]:
                return True
            # Multiple workers can observe a missing collection at the same
            # time. Qdrant returns 409 when the other worker wins the create
            # race; that is a successful ensure operation, provided the
            # collection is now readable.
            if response.status_code == 409:
                # A newly created collection can briefly return 500 while
                # Qdrant finishes initialization. Poll instead of turning a
                # successful create race into a document-processing failure.
                for _ in range(15):
                    if await self.collection_exists():
                        return True
                    await asyncio.sleep(1)
                return False
            return False
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError):
            return False

    async def collection_exists(self) -> bool:
        """检查集合是否存在"""
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.config.qdrant_url}/collections/{self.collection_name}"
            )
            return response.status_code == 200
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError):
            return False

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None


class QdrantVectorStore(VectorStore):
    """Qdrant向量存储实现"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def search_with_payload(
        self,
        query_vector: List[float],
        top_k: int = 5,
        with_vectors: bool = False
    ) -> List[Dict[str, Any]]:
        """带payload的搜索"""
        client = await self._get_client()

        try:
            response = await client.post(
                f"{self.config.qdrant_url}/collections/{self.collection_name}/points/search",
                json={
                    "vector": query_vector,
                    "limit": top_k,
                    "with_payload": True,
                    "with_vectors": with_vectors
                }
            )

            if response.status_code == 200:
                return response.json().get("result", [])
            return []
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError):
            return []


class MemoryVectorStore:
    """内存中的向量存储实现 - 全局单例模式"""

    _instances = {}
    _access_order: List[str] = []
    _lock = threading.Lock()
    MAX_INSTANCES = 10

    @classmethod
    def get_instance(cls, collection_name: str, embedding_service=None):
        """获取或创建指定集合的内存向量存储实例（限制最多 MAX_INSTANCES 个，超出淘汰最久未访问的）"""
        with cls._lock:
            if collection_name in cls._instances:
                # 更新访问顺序
                if collection_name in cls._access_order:
                    cls._access_order.remove(collection_name)
                cls._access_order.append(collection_name)
                return cls._instances[collection_name]

            # 超过上限，淘汰最久未访问的
            if len(cls._instances) >= cls.MAX_INSTANCES:
                if cls._access_order:
                    oldest = cls._access_order.pop(0)
                    removed = cls._instances.pop(oldest, None)
                    if removed:
                        removed.points.clear()
                        logger.warning(
                            "MemoryVectorStore 淘汰实例: %s (当前 %d 个)",
                            oldest, len(cls._instances),
                        )

            instance = cls(collection_name=collection_name, embedding_service=embedding_service)
            cls._instances[collection_name] = instance
            cls._access_order.append(collection_name)
            return instance

    @classmethod
    def clear_all(cls):
        """清空所有实例（用于测试）"""
        with cls._lock:
            for inst in cls._instances.values():
                inst.points.clear()
            cls._instances.clear()
            cls._access_order.clear()

    def __init__(self, collection_name: str = None, embedding_service=None):
        from core.rag_config import get_rag_config
        self.config = get_rag_config()
        self.collection_name = collection_name or self.config.collection_name
        self.embedding_service = embedding_service
        self.points = []

    def upsert(
        self,
        points: List[Dict[str, Any]],
        wait: bool = True
    ) -> bool:
        """插入或更新向量"""
        for point in points:
            existing_index = next((i for i, p in enumerate(self.points) if p.get("id") == point.get("id")), None)
            if existing_index is not None:
                self.points[existing_index] = point
            else:
                self.points.append(point)
        return True

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索"""
        import numpy as np

        logger.debug(
            "MemoryVectorStore 搜索开始: collection=%s total_points=%s filters=%s",
            self.collection_name,
            len(self.points),
            filters,
        )

        filtered_points = self.points
        if filters:
            filtered_points = [p for p in self.points if self._matches_filter(p, filters)]
            logger.debug("MemoryVectorStore 过滤后点数: %s", len(filtered_points))

        results = []
        for point in filtered_points:
            vector = point.get("vector", [])
            if not vector:
                continue

            similarity = self._cosine_similarity(query_vector, vector)
            point_id = str(point.get("id", ""))[:8]
            logger.debug("MemoryVectorStore 点 %s... 相似度: %.4f", point_id, similarity)

            if score_threshold is None or similarity >= score_threshold:
                results.append({
                    "id": point.get("id"),
                    "score": similarity,
                    "payload": point.get("payload", {})
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        logger.debug("MemoryVectorStore 返回 %s 个结果", len(results[:top_k]))
        return results[:top_k]

    def delete(self, point_ids: List[str], wait: bool = True) -> bool:
        """删除向量"""
        self.points = [p for p in self.points if p.get("id") not in point_ids]
        return True

    def create_collection(self, vector_size: Optional[int] = None) -> bool:
        """创建集合"""
        return True

    def collection_exists(self) -> bool:
        """检查集合是否存在"""
        return True

    def _matches_filter(self, point: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """检查点是否匹配过滤器"""
        payload = point.get("payload", {})
        for key, value in filters.items():
            if isinstance(value, dict) and "$in" in value:
                if payload.get(key) not in value["$in"]:
                    return False
            elif payload.get(key) != value:
                return False
        return True

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        import numpy as np
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)


class EmbeddedQdrantStore:
    """嵌入式Qdrant向量存储 - 无需Docker"""

    def __init__(self, collection_name: Optional[str] = None, embedding_service: Optional[EmbeddingService] = None, storage_path: str = "./qdrant_data"):
        self.config = get_rag_config()
        self.collection_name = collection_name or self.config.collection_name
        self.embedding_service = embedding_service or EmbeddingService()
        self.storage_path = storage_path
        self._client = None
        self._vector_size = 512

    def _get_client(self):
        """获取Qdrant客户端 - 使用全局单例"""
        return QdrantClientManager.get_client(self.storage_path)

    def upsert(
        self,
        points: List[Dict[str, Any]],
        wait: bool = True
    ) -> bool:
        """插入或更新向量"""
        from qdrant_client.models import PointStruct
        import uuid
        
        client = self._get_client()
        
        try:
            qdrant_points = []
            for p in points:
                point_id = p.get("id")
                # 确保ID是UUID格式
                if not isinstance(point_id, uuid.UUID):
                    try:
                        point_id = uuid.UUID(str(point_id))
                    except ValueError:
                        # 如果不是有效的UUID，生成一个新的
                        point_id = uuid.uuid4()
                
                qdrant_points.append(PointStruct(
                    id=point_id,
                    vector=p.get("vector", []),
                    payload=p.get("payload", {})
                ))
            
            client.upsert(
                collection_name=self.collection_name,
                points=qdrant_points
            )
            return True
        except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"EmbeddedQdrantStore upsert error: {e}", exc_info=True)
            return False

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        score_threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索"""
        client = self._get_client()
        
        try:
            qdrant_filter = None
            if filters:
                from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
                conditions = []
                for key, value in filters.items():
                    if isinstance(value, dict) and "$in" in value:
                        conditions.append(FieldCondition(
                            key=key,
                            match=MatchAny(any=value["$in"])
                        ))
                    else:
                        conditions.append(FieldCondition(
                            key=key,
                            match=MatchValue(value=value)
                        ))
                if conditions:
                    qdrant_filter = Filter(must=conditions)

            results = client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=qdrant_filter
            )
            
            return [
                {
                    "id": str(r.id),
                    "score": r.score,
                    "payload": r.payload or {}
                }
                for r in results.points
            ]
        except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"EmbeddedQdrantStore search error: {e}", exc_info=True)
            return []

    def delete(self, point_ids: List[str], wait: bool = True) -> bool:
        """删除向量"""
        client = self._get_client()
        import uuid
        
        try:
            # 转换为UUID
            uuid_ids = []
            for pid in point_ids:
                try:
                    uuid_ids.append(uuid.UUID(str(pid)))
                except ValueError:
                    pass
            
            if uuid_ids:
                client.delete(
                    collection_name=self.collection_name,
                    points_selector=uuid_ids
                )
            return True
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"EmbeddedQdrantStore delete error: {e}", exc_info=True)
            return False

    def create_collection(self, vector_size: Optional[int] = None) -> bool:
        """创建集合"""
        from qdrant_client.models import Distance, VectorParams
        
        client = self._get_client()
        size = vector_size or self._vector_size
        
        try:
            if not client.collection_exists(self.collection_name):
                client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=size, distance=Distance.COSINE)
                )
            return True
        except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"EmbeddedQdrantStore create_collection error: {e}", exc_info=True)
            return False

    def collection_exists(self) -> bool:
        """检查集合是否存在"""
        client = self._get_client()
        try:
            return client.collection_exists(self.collection_name)
        except (RuntimeError, ValueError, TypeError, AttributeError):
            return False

    def close(self):
        """关闭客户端"""
        if self._client:
            self._client.close()
            self._client = None


async def create_vector_store(
    collection_name: Optional[str] = None,
    embedding_service: Optional[EmbeddingService] = None,
    use_memory_fallback: bool = True
):
    """
    创建向量存储实例，带 Qdrant 不可用时回退到 MemoryVectorStore

    优先级（保证 API server 与 Celery worker 使用同一存储）：
    1. QdrantVectorStore（HTTP 连接，Docker 时使用）—— 多进程共享
    2. EmbeddedQdrantStore（本地文件，无 Docker 时使用）—— 单进程独占，多进程互斥
    3. MemoryVectorStore（仅作最后兜底，不跨进程共享）

    Args:
        collection_name: 集合名称
        embedding_service: 嵌入服务
        use_memory_fallback: 是否启用内存回退

    Returns:
        VectorStore 实例
    """
    # ── 1. 尝试使用 QdrantVectorStore（HTTP 连接，Docker 时使用）──
    try:
        logger.info("尝试使用 HTTP QdrantVectorStore...")
        store = QdrantVectorStore(
            collection_name=collection_name,
            embedding_service=embedding_service
        )
        await store.collection_exists()
        logger.info("✅ HTTP QdrantVectorStore 连接成功")
        return store
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
        logger.warning(f"⚠️ HTTP QdrantVectorStore 连接失败: {e}")
        # 失败时释放已创建的 HTTP 连接，避免连接池泄漏
        try:
            if 'store' in locals():
                await store.close()
        except Exception:
            pass

    # ── 2. 尝试使用 EmbeddedQdrantStore（本地文件，无 Docker 时使用）──
    try:
        logger.info("尝试使用 EmbeddedQdrantStore...")
        store = EmbeddedQdrantStore(
            collection_name=collection_name,
            embedding_service=embedding_service
        )
        store.collection_exists()
        logger.info("✅ EmbeddedQdrantStore 连接成功")
        return store
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
        logger.warning(f"⚠️ EmbeddedQdrantStore 连接失败: {e}")
        try:
            if 'store' in locals():
                store.close()
        except Exception:
            pass

    # ── 3. 最后回退到 MemoryVectorStore（仅限单进程场景）────────────
    if use_memory_fallback:
        logger.warning(
            "⚠️ 所有 Qdrant 后端均不可用，退化为 MemoryVectorStore（数据不跨进程共享）"
        )
        return MemoryVectorStore.get_instance(
            collection_name=collection_name,
            embedding_service=embedding_service
        )

    raise RuntimeError("无法创建向量存储实例，请检查 Qdrant 服务")
