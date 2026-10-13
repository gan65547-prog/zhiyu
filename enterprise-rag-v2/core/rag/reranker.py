"""
文档重排序

提供文档重排序功能以提高检索质量
"""

from typing import List, Optional
import httpx

from core.rag_config import get_rag_config
from core.interfaces.rag_engine import RetrievedDocument
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class DocumentReranker:
    """文档重排序器"""

    def __init__(self, model_name: Optional[str] = None):
        self.config = get_rag_config()
        self.model_name = model_name or self.config.rerank_model
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端，带连接池限制"""
        if self._client is None:
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
            self._client = httpx.AsyncClient(timeout=30.0, limits=limits)
        return self._client

    async def rerank(
        self,
        query: str,
        documents: List[RetrievedDocument],
        top_k: Optional[int] = None
    ) -> List[RetrievedDocument]:
        """重排序文档"""
        if not documents:
            return []

        if len(documents) == 1:
            return documents

        try:
            client = await self._get_client()

            doc_texts = [
                {
                    "id": doc.id,
                    "text": doc.content[:500]
                }
                for doc in documents
            ]

            response = await client.post(
                f"{self.config.llm_url}/api/rerank",
                json={
                    "model": self.model_name,
                    "query": query,
                    "documents": [d["text"] for d in doc_texts],
                    "top_k": top_k or len(documents)
                }
            )

            if response.status_code == 200:
                results = response.json().get("results", [])
                id_to_doc = {doc.id: doc for doc in documents}

                reranked = []
                for r in results:
                    doc_id = doc_texts[r.get("index", 0)]["id"]
                    if doc_id in id_to_doc:
                        doc = id_to_doc[doc_id]
                        doc.score = r.get("relevance_score", doc.score)
                        reranked.append(doc)

                return reranked
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError):
            logger.exception("文档重排序失败，返回原始顺序")

        return documents

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None


class SimpleReranker(DocumentReranker):
    """简单的重排序器（当无法连接重排序服务时使用）"""

    def __init__(self):
        super().__init__()

    async def rerank(
        self,
        query: str,
        documents: List[RetrievedDocument],
        top_k: Optional[int] = None
    ) -> List[RetrievedDocument]:
        """基于关键词匹配的重排序"""
        query_terms = set(query.lower().split())

        for doc in documents:
            content_terms = set(doc.content.lower().split())
            overlap = len(query_terms & content_terms)
            doc.score = doc.score * (1 + overlap * 0.1)

        documents.sort(key=lambda d: d.score, reverse=True)

        if top_k:
            return documents[:top_k]
        return documents
