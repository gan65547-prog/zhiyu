"""
RAG引擎实现

整合检索、重排序和生成功能
"""

import time
from typing import List, Optional, Dict, Any, AsyncIterator
from uuid import UUID

from core.rag_config import get_rag_config, is_effective_openai_api_key
from core.rag.embedding import EmbeddingService, OllamaEmbedding, DeepSeekEmbedding
from core.rag.vector_store import VectorStore, QdrantVectorStore
from core.rag.reranker import DocumentReranker, SimpleReranker
from core.rag.llm_provider import OllamaLLMProvider, DeepSeekProvider, OpenAIProvider
from core.rag.document_processor import DocumentProcessor
from infrastructure.logging.logger import get_logger
from core.interfaces.rag_engine import (
    RAGEngine as RAGEngineInterface,
    DocumentRetriever,
    DocumentReranker as RerankerInterface,
    ResponseGenerator,
    EmbeddingProvider,
    DocumentProcessor as DocProcessorInterface,
    TextSplitter,
    RetrievedDocument,
    QueryContext,
    RAGResponse,
)

logger = get_logger(__name__)


class RAGEngineImpl(RAGEngineInterface):
    """RAG引擎实现"""

    def __init__(
        self,
        embedding_service: Optional[EmbeddingProvider] = None,
        vector_store: Optional[VectorStore] = None,
        reranker: Optional[DocumentReranker] = None,
        response_generator: Optional[ResponseGenerator] = None,
        document_processor: Optional[DocumentProcessor] = None,
        db_session=None,
        runtime_provider: Optional[str] = None,
        runtime_api_key: Optional[str] = None,
        runtime_base_url: Optional[str] = None,
        runtime_model: Optional[str] = None,
    ):
        self.config = get_rag_config()
        self.db_session = db_session

        provider_key = (runtime_provider or "deepseek").strip().lower()
        use_runtime_llm = is_effective_openai_api_key(runtime_api_key) and provider_key in {"deepseek", "openai"}
        use_remote_llm = use_runtime_llm or is_effective_openai_api_key(self.config.deepseek_api_key)
        # 优先使用 OpenAI 兼容远端（DeepSeek 等）；密钥缺失或为仓库占位符时用本地 BGE 模型
        if use_remote_llm:
            self.embedding_service = embedding_service or DeepSeekEmbedding(api_key=runtime_api_key)
            if response_generator:
                self.response_generator = response_generator
            elif use_runtime_llm and provider_key == "openai":
                self.response_generator = OpenAIProvider(
                    api_key=runtime_api_key,
                    model=runtime_model,
                    base_url=runtime_base_url,
                )
            else:
                self.response_generator = DeepSeekProvider(
                    api_key=runtime_api_key,
                    model=runtime_model,
                    base_url=runtime_base_url,
                )
        else:
            if self.config.deepseek_api_key:
                logger.info(
                    "OPENAI_API_KEY 未配置或为占位符，使用本地 BGE 模型作为嵌入；"
                    "若需 DeepSeek 请在 .env 填入长度约 40 字符以上的真实密钥。"
                )
            from core.rag.embedding import BGESmallZhEmbedding
            self.embedding_service = embedding_service or BGESmallZhEmbedding()
            self.response_generator = response_generator or OllamaLLMProvider()
        
        # 默认使用 Qdrant 向量存储
        self.vector_store = vector_store or QdrantVectorStore(
            embedding_service=self.embedding_service
        )
        # 注意：Qdrant 可用性检查将在首次使用时进行
        self.reranker = reranker or SimpleReranker()
        self.document_processor = document_processor or DocumentProcessor()

    async def close(self):
        """释放所有 HTTP 客户端资源，防止连接池泄漏"""
        import asyncio
        import inspect
        tasks = []
        if hasattr(self.response_generator, 'close') and callable(self.response_generator.close):
            result = self.response_generator.close()
            if inspect.isawaitable(result):
                tasks.append(result)
        if hasattr(self.vector_store, 'close') and callable(self.vector_store.close):
            result = self.vector_store.close()
            if inspect.isawaitable(result):
                tasks.append(result)
        if hasattr(self.reranker, 'close') and callable(self.reranker.close):
            result = self.reranker.close()
            if inspect.isawaitable(result):
                tasks.append(result)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def _inject_errata_warnings(self, documents: List[RetrievedDocument]) -> None:
        """将活跃勘误注入到检索文档的 metadata 中，供提示词模板使用"""
        if not self.db_session:
            return

        doc_ids = list({doc.document_id for doc in documents if doc.document_id})
        if not doc_ids:
            return

        try:
            from services.impl.errata_service import ErrataService
            errata_service = ErrataService(self.db_session)
            errata_map = await errata_service.get_active_errata_for_documents(doc_ids)

            for doc in documents:
                if doc.document_id in errata_map:
                    doc.metadata["_errata"] = errata_map[doc.document_id]
                    logger.info(
                        f"Document {doc.document_id} has {len(errata_map[doc.document_id])} active errata"
                    )
        except Exception as e:
            logger.warning(f"Failed to inject errata warnings: {e}", exc_info=True)

    async def _get_document_name_from_db(self, document_id: str) -> str:
        """从数据库获取文档名称"""
        if not self.db_session:
            logger.warning("db_session 为空")
            return "未知文档"
        
        if not document_id:
            logger.warning("document_id 为空")
            return "未知文档"
        
        try:
            from sqlalchemy import select
            from infrastructure.database.models import Document
            
            logger.info(f"尝试查询数据库查询文档, document_id: {document_id}")
            
            result = await self.db_session.execute(
                select(Document).where(Document.id == document_id)
            )
            doc = result.scalar_one_or_none()
            
            if doc:
                logger.info(f"找到文档, file_name: {doc.file_name}")
                if doc.file_name:
                    return doc.file_name
                else:
                    logger.warning("文档存在但 file_name 为空")
            else:
                logger.warning(f"未找到文档, document_id: {document_id}")
        except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"从数据库查询文档名称失败: {e}", exc_info=True)
        
        return "未知文档"

    async def query(
        self,
        query: str,
        context: QueryContext,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> RAGResponse:
        """执行RAG查询"""
        start_time = time.time()
        retrieval_start = start_time

        documents = await self.retrieve(query, context)

        await self._inject_errata_warnings(documents)

        retrieval_time = int((time.time() - retrieval_start) * 1000)

        generation_start = time.time()
        answer = await self.response_generator.generate(
            query=query,
            documents=documents,
            conversation_history=conversation_history,
            temperature=temperature,
            max_tokens=max_tokens
        )

        generation_time = int((time.time() - generation_start) * 1000)
        total_time = int((time.time() - start_time) * 1000)

        return RAGResponse(
            answer=answer,
            retrieved_documents=documents,
            tokens_used=len(answer) // 4,
            retrieval_time_ms=retrieval_time,
            generation_time_ms=generation_time,
            metadata={
                "retrieval_mode": context.retrieval_mode,
                "top_k": context.top_k,
                "total_time_ms": total_time
            }
        )

    async def query_stream(
        self,
        query: str,
        context: QueryContext,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        """流式执行RAG查询"""
        retrieval_start = time.time()

        documents = await self.retrieve(query, context)

        await self._inject_errata_warnings(documents)

        retrieval_time = int((time.time() - retrieval_start) * 1000)

        yield {
            "type": "retrieval",
            "retrieved_count": len(documents),
            "retrieval_time_ms": retrieval_time,
            "documents": [
                {
                    "id": doc.id,
                    "content": doc.content,
                    "score": doc.score,
                    "metadata": doc.metadata,
                    "document_id": doc.document_id,
                    "document_name": doc.document_name,
                    "chunk_index": doc.chunk_index,
                }
                for doc in documents
            ],
        }

        async for token in self.response_generator.generate_stream(
            query=query,
            documents=documents,
            conversation_history=conversation_history,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            yield {"type": "token", "delta": token}

    async def retrieve(
        self,
        query: str,
        context: QueryContext
    ) -> List[RetrievedDocument]:
        """检索相关文档"""
        if context.retrieval_mode == "semantic":
            return await self.semantic_search(query, context)
        elif context.retrieval_mode == "keyword":
            return await self.keyword_search(query, context)
        else:
            semantic_results = await self.semantic_search(query, context)
            keyword_results = await self.keyword_search(query, context)

            merged = self._merge_results(semantic_results, keyword_results)
            return merged

    async def semantic_search(
        self,
        query: str,
        context: QueryContext
    ) -> List[RetrievedDocument]:
        """语义检索"""
        query_vector = await self.embedding_service.embed_text(query)
        
        filters = None
        if context.dataset_ids and len(context.dataset_ids) > 0:
            dataset_id_strs = [str(did) for did in context.dataset_ids]
            if len(dataset_id_strs) == 1:
                filters = {"dataset_id": dataset_id_strs[0]}
            else:
                filters = {"dataset_id": {"$in": dataset_id_strs}}
        
        try:
            results = await self.vector_store.search(
                query_vector=query_vector,
                top_k=context.top_k * 2,
                score_threshold=context.similarity_threshold,
                filters=filters
            )
            if not results and context.similarity_threshold is not None:
                logger.info("相似度阈值下没有结果，保留同一数据集过滤条件重试无阈值检索")
                results = await self.vector_store.search(
                    query_vector=query_vector,
                    top_k=context.top_k * 2,
                    score_threshold=None,
                    filters=filters
                )
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning("Qdrant 语义检索失败，切换到内存向量存储: %s", e, exc_info=True)
            from core.rag.vector_store import MemoryVectorStore
            self.vector_store = MemoryVectorStore(
                embedding_service=self.embedding_service
            )
            results = await self.vector_store.search(
                query_vector=query_vector,
                top_k=context.top_k * 2,
                score_threshold=context.similarity_threshold,
                filters=filters
            )
            if not results and context.similarity_threshold is not None:
                logger.info("关键词检索阈值下没有结果，保留同一数据集过滤条件重试无阈值检索")
                results = await self.vector_store.search(
                    query_vector=query_vector,
                    top_k=context.top_k * 2,
                    score_threshold=None,
                    filters=filters
                )

        documents = []
        for i, r in enumerate(results):
            payload = r.get("payload", {})
            doc_id = payload.get("document_id", "")
            
            # 优先从 payload 获取，如果没有则从数据库查询
            doc_name = payload.get("document_name", "")
            if not doc_name:
                doc_name = await self._get_document_name_from_db(doc_id)
            
            logger.info(f"检索结果 {i+1} - payload keys: {list(payload.keys())}")
            logger.info(f"检索结果 {i+1} - document_id: {doc_id}")
            logger.info(f"检索结果 {i+1} - document_name (最终): {doc_name}")
            
            documents.append(RetrievedDocument(
                id=r["id"],
                content=payload.get("content", ""),
                metadata=payload.get("metadata", {}),
                score=r.get("score", 0.0),
                document_id=doc_id,
                document_name=doc_name,
                chunk_index=payload.get("chunk_index", 0)
            ))

        if context.rerank and len(documents) > 1:
            documents = await self.reranker.rerank(query, documents, context.top_k)

        return documents[:context.top_k]

    async def keyword_search(
        self,
        query: str,
        context: QueryContext
    ) -> List[RetrievedDocument]:
        """关键词检索（简化为向量搜索）"""
        query_vector = await self.embedding_service.embed_text(query)
        
        filters = None
        if context.dataset_ids and len(context.dataset_ids) > 0:
            dataset_id_strs = [str(did) for did in context.dataset_ids]
            if len(dataset_id_strs) == 1:
                filters = {"dataset_id": dataset_id_strs[0]}
            else:
                filters = {"dataset_id": {"$in": dataset_id_strs}}
        
        try:
            results = await self.vector_store.search(
                query_vector=query_vector,
                top_k=context.top_k * 2,
                score_threshold=context.similarity_threshold,
                filters=filters
            )
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning("Qdrant 关键词检索失败，切换到内存向量存储: %s", e, exc_info=True)
            from core.rag.vector_store import MemoryVectorStore
            self.vector_store = MemoryVectorStore(
                embedding_service=self.embedding_service
            )
            results = await self.vector_store.search(
                query_vector=query_vector,
                top_k=context.top_k * 2,
                score_threshold=context.similarity_threshold,
                filters=filters
            )

        documents = []
        for i, r in enumerate(results):
            payload = r.get("payload", {})
            doc_id = payload.get("document_id", "")
            
            # 优先从 payload 获取，如果没有则从数据库查询
            doc_name = payload.get("document_name", "")
            if not doc_name:
                doc_name = await self._get_document_name_from_db(doc_id)
            
            logger.info(f"检索结果 {i+1} - payload keys: {list(payload.keys())}")
            logger.info(f"检索结果 {i+1} - document_id: {doc_id}")
            logger.info(f"检索结果 {i+1} - document_name (最终): {doc_name}")
            
            documents.append(RetrievedDocument(
                id=r["id"],
                content=payload.get("content", ""),
                metadata=payload.get("metadata", {}),
                score=r.get("score", 0.0),
                document_id=doc_id,
                document_name=doc_name,
                chunk_index=payload.get("chunk_index", 0)
            ))

        if context.rerank and len(documents) > 1:
            documents = await self.reranker.rerank(query, documents, context.top_k)

        return documents[:context.top_k]

    def _merge_results(
        self,
        semantic_results: List[RetrievedDocument],
        keyword_results: List[RetrievedDocument]
    ) -> List[RetrievedDocument]:
        """合并语义检索和关键词检索结果"""
        seen_ids = set()
        merged = []

        for doc in semantic_results:
            if doc.id not in seen_ids:
                merged.append(doc)
                seen_ids.add(doc.id)

        for doc in keyword_results:
            if doc.id not in seen_ids:
                merged.append(doc)
                seen_ids.add(doc.id)

        return merged


class DocumentRetrieverImpl(DocumentRetriever):
    """文档检索器实现"""

    def __init__(self, vector_store: VectorStore, embedding_service: EmbeddingService):
        self.vector_store = vector_store
        self.embedding_service = embedding_service

    async def retrieve(
        self,
        query: str,
        context: QueryContext
    ) -> List[RetrievedDocument]:
        """检索文档"""
        if context.retrieval_mode == "semantic":
            return await self.semantic_search(await self.embedding_service.embed_text(query), context)
        elif context.retrieval_mode == "keyword":
            return await self.keyword_search(query, context)
        else:
            semantic = await self.semantic_search(await self.embedding_service.embed_text(query), context)
            keyword = await self.keyword_search(query, context)
            return self._merge(semantic, keyword)

    async def semantic_search(
        self,
        query_embedding: List[float],
        context: QueryContext
    ) -> List[RetrievedDocument]:
        """语义检索"""
        results = await self.vector_store.search(
            query_vector=query_embedding,
            top_k=context.top_k,
            score_threshold=context.similarity_threshold
        )

        return [
            RetrievedDocument(
                id=r["id"],
                content=r.get("payload", {}).get("content", ""),
                metadata=r.get("payload", {}).get("metadata", {}),
                score=r.get("score", 0.0),
                document_id=r.get("payload", {}).get("document_id", ""),
                document_name=r.get("payload", {}).get("document_name", ""),
                chunk_index=r.get("payload", {}).get("chunk_index", 0)
            )
            for r in results
        ]

    async def keyword_search(
        self,
        query: str,
        context: QueryContext
    ) -> List[RetrievedDocument]:
        """关键词检索"""
        return await self.semantic_search(
            await self.embedding_service.embed_text(query),
            context
        )

    def _merge(
        self,
        semantic: List[RetrievedDocument],
        keyword: List[RetrievedDocument]
    ) -> List[RetrievedDocument]:
        """合并结果"""
        seen = set()
        result = []
        for doc in semantic:
            if doc.id not in seen:
                result.append(doc)
                seen.add(doc.id)
        for doc in keyword:
            if doc.id not in seen:
                result.append(doc)
                seen.add(doc.id)
        return result


class DocumentRerankerImpl(RerankerInterface):
    """文档重排序器实现"""

    def __init__(self, reranker: DocumentReranker):
        self.reranker = reranker

    async def rerank(
        self,
        query: str,
        documents: List[RetrievedDocument]
    ) -> List[RetrievedDocument]:
        """重排序"""
        return await self.reranker.rerank(query, documents)


class ResponseGeneratorImpl(ResponseGenerator):
    """响应生成器实现"""

    def __init__(self, generator: OllamaLLMProvider):
        self.generator = generator

    async def generate(
        self,
        query: str,
        documents: List[RetrievedDocument],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """生成响应"""
        return await self.generator.generate(
            query=query,
            documents=documents,
            conversation_history=conversation_history,
            temperature=temperature,
            max_tokens=max_tokens
        )

    async def generate_stream(
        self,
        query: str,
        documents: List[RetrievedDocument],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        """流式生成"""
        async for token in self.generator.generate_stream(
            query=query,
            documents=documents,
            conversation_history=conversation_history,
            temperature=temperature,
            max_tokens=max_tokens
        ):
            yield token
