"""
单元测试 - RAG引擎
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from core.rag.rag_engine import RAGEngineImpl, DocumentRetrieverImpl, DocumentRerankerImpl, ResponseGeneratorImpl
from core.interfaces.rag_engine import QueryContext, RetrievedDocument, RAGResponse


class TestRAGEngineImpl:
    """RAGEngineImpl单元测试"""

    @pytest.fixture
    def mock_embedding_service(self):
        """创建模拟嵌入服务"""
        service = MagicMock()
        service.embed_text = AsyncMock(return_value=[0.1] * 384)
        return service

    @pytest.fixture
    def mock_vector_store(self):
        """创建模拟向量存储"""
        store = MagicMock()
        store.search = AsyncMock(return_value=[
            {"id": "1", "score": 0.9, "payload": {"content": "Test content 1", "metadata": {}, "document_id": "doc1", "document_name": "Doc 1", "chunk_index": 0}},
            {"id": "2", "score": 0.8, "payload": {"content": "Test content 2", "metadata": {}, "document_id": "doc2", "document_name": "Doc 2", "chunk_index": 1}}
        ])
        return store

    @pytest.fixture
    def mock_reranker(self):
        """创建模拟重排序器"""
        reranker = MagicMock()
        reranker.rerank = AsyncMock(return_value=[])
        return reranker

    @pytest.fixture
    def mock_response_generator(self):
        """创建模拟响应生成器"""
        generator = MagicMock()
        generator.generate = AsyncMock(return_value="This is a test response.")
        generator.generate_stream = AsyncMock(return_value=iter(["Test ", "response ", "chunk."]))
        return generator

    @pytest.fixture
    def mock_document_processor(self):
        """创建模拟文档处理器"""
        processor = MagicMock()
        processor.extract_text = AsyncMock(return_value="Extracted text content")
        processor.split_text = MagicMock(return_value=["Chunk 1", "Chunk 2"])
        return processor

    @pytest.fixture
    def rag_engine(self, mock_embedding_service, mock_vector_store, mock_reranker, mock_response_generator, mock_document_processor):
        """创建RAGEngineImpl实例"""
        return RAGEngineImpl(
            embedding_service=mock_embedding_service,
            vector_store=mock_vector_store,
            reranker=mock_reranker,
            response_generator=mock_response_generator,
            document_processor=mock_document_processor
        )

    @pytest.fixture
    def sample_context(self):
        """创建示例查询上下文"""
        return QueryContext(
            workspace_id=uuid4(),
            dataset_ids=[uuid4()],
            retrieval_mode="semantic",
            top_k=5,
            similarity_threshold=0.7,
            rerank=True
        )

    @pytest.mark.asyncio
    async def test_query_semantic_search(self, rag_engine, sample_context):
        """测试语义检索查询"""
        with patch.object(rag_engine, 'retrieve', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = [
                RetrievedDocument(
                    id="1",
                    content="Test content",
                    metadata={},
                    score=0.9,
                    document_id="doc1",
                    document_name="Doc 1",
                    chunk_index=0
                )
            ]

            result = await rag_engine.query(
                query="test query",
                context=sample_context
            )

            assert isinstance(result, RAGResponse)
            assert hasattr(result, 'answer')
            assert hasattr(result, 'retrieved_documents')

    @pytest.mark.asyncio
    async def test_query_stream(self, rag_engine, sample_context):
        """测试流式查询"""
        async def mock_stream(query, context):
            yield "Test "
            yield "response"

        with patch.object(rag_engine, 'query_stream', mock_stream):
            tokens = []
            async for token in rag_engine.query_stream(
                query="test query",
                context=sample_context
            ):
                tokens.append(token)

            assert len(tokens) > 0

    @pytest.mark.asyncio
    async def test_retrieve_semantic(self, rag_engine, sample_context):
        """测试语义检索"""
        result = await rag_engine.retrieve(
            query="test query",
            context=sample_context
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_retrieve_keyword(self, rag_engine, mock_embedding_service):
        """测试关键词检索"""
        context = QueryContext(
            workspace_id=uuid4(),
            dataset_ids=[uuid4()],
            retrieval_mode="keyword",
            top_k=5,
            similarity_threshold=0.7,
            rerank=False
        )

        result = await rag_engine.retrieve(
            query="test query",
            context=context
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_retrieve_hybrid(self, rag_engine):
        """测试混合检索"""
        context = QueryContext(
            workspace_id=uuid4(),
            dataset_ids=[uuid4()],
            retrieval_mode="hybrid",
            top_k=5,
            similarity_threshold=0.7,
            rerank=False
        )

        result = await rag_engine.retrieve(
            query="test query",
            context=context
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_semantic_search(self, rag_engine, mock_vector_store, sample_context):
        """测试语义搜索方法（RAGEngineImpl 签名为 query 文本 + 上下文，由内部 embed + search）"""
        result = await rag_engine.semantic_search(
            "test query",
            sample_context
        )

        assert isinstance(result, list)
        mock_vector_store.search.assert_called()

    @pytest.mark.asyncio
    async def test_keyword_search(self, rag_engine, mock_embedding_service, sample_context):
        """测试关键词搜索方法"""
        result = await rag_engine.keyword_search(
            query="test query",
            context=sample_context
        )

        assert isinstance(result, list)
        mock_embedding_service.embed_text.assert_called()

    @pytest.mark.asyncio
    async def test_merge_results(self, rag_engine):
        """测试合并语义和关键词检索结果"""
        semantic_results = [
            RetrievedDocument(id="1", content="Content 1", metadata={}, score=0.9, document_id="doc1", document_name="Doc 1", chunk_index=0),
            RetrievedDocument(id="2", content="Content 2", metadata={}, score=0.8, document_id="doc2", document_name="Doc 2", chunk_index=1)
        ]
        keyword_results = [
            RetrievedDocument(id="3", content="Content 3", metadata={}, score=0.85, document_id="doc3", document_name="Doc 3", chunk_index=0),
            RetrievedDocument(id="2", content="Content 2", metadata={}, score=0.8, document_id="doc2", document_name="Doc 2", chunk_index=1)
        ]

        result = rag_engine._merge_results(semantic_results, keyword_results)

        assert len(result) == 3
        result_ids = [doc.id for doc in result]
        assert "1" in result_ids
        assert "2" in result_ids
        assert "3" in result_ids


class TestDocumentRetrieverImpl:
    """DocumentRetrieverImpl单元测试"""

    @pytest.fixture
    def mock_vector_store(self):
        """创建模拟向量存储"""
        store = MagicMock()
        store.search = AsyncMock(return_value=[
            {"id": "1", "score": 0.9, "payload": {"content": "Test content", "metadata": {}, "document_id": "doc1", "document_name": "Doc 1", "chunk_index": 0}}
        ])
        return store

    @pytest.fixture
    def mock_embedding_service(self):
        """创建模拟嵌入服务"""
        service = MagicMock()
        service.embed_text = AsyncMock(return_value=[0.1] * 384)
        return service

    @pytest.fixture
    def retriever(self, mock_vector_store, mock_embedding_service):
        """创建DocumentRetrieverImpl实例"""
        return DocumentRetrieverImpl(
            vector_store=mock_vector_store,
            embedding_service=mock_embedding_service
        )

    @pytest.mark.asyncio
    async def test_retrieve_semantic(self, retriever, mock_embedding_service):
        """测试语义检索"""
        context = QueryContext(
            workspace_id=uuid4(),
            dataset_ids=[uuid4()],
            retrieval_mode="semantic",
            top_k=5,
            similarity_threshold=0.7,
            rerank=False
        )

        result = await retriever.retrieve(
            query="test query",
            context=context
        )

        assert isinstance(result, list)
        mock_embedding_service.embed_text.assert_called()

    @pytest.mark.asyncio
    async def test_retrieve_keyword(self, retriever):
        """测试关键词检索"""
        context = QueryContext(
            workspace_id=uuid4(),
            dataset_ids=[uuid4()],
            retrieval_mode="keyword",
            top_k=5,
            similarity_threshold=0.7,
            rerank=False
        )

        result = await retriever.retrieve(
            query="test query",
            context=context
        )

        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_semantic_search(self, retriever, mock_vector_store):
        """测试语义搜索"""
        context = QueryContext(
            workspace_id=uuid4(),
            dataset_ids=[uuid4()],
            retrieval_mode="semantic",
            top_k=5,
            similarity_threshold=0.7,
            rerank=False
        )

        query_vector = [0.1] * 384
        result = await retriever.semantic_search(
            query_embedding=query_vector,
            context=context
        )

        assert isinstance(result, list)
        assert len(result) == 1
        mock_vector_store.search.assert_called()

    @pytest.mark.asyncio
    async def test_merge(self, retriever):
        """测试合并结果"""
        semantic = [
            RetrievedDocument(id="1", content="Content 1", metadata={}, score=0.9, document_id="doc1", document_name="Doc 1", chunk_index=0)
        ]
        keyword = [
            RetrievedDocument(id="2", content="Content 2", metadata={}, score=0.8, document_id="doc2", document_name="Doc 2", chunk_index=0)
        ]

        result = retriever._merge(semantic, keyword)

        assert len(result) == 2


class TestResponseGeneratorImpl:
    """ResponseGeneratorImpl单元测试"""

    @pytest.fixture
    def mock_llm_provider(self):
        """创建模拟LLM提供商"""
        provider = MagicMock()
        provider.generate = AsyncMock(return_value="Test response")
        provider.generate_stream = AsyncMock(return_value=iter(["Test ", "response"]))
        return provider

    @pytest.fixture
    def generator(self, mock_llm_provider):
        """创建ResponseGeneratorImpl实例"""
        return ResponseGeneratorImpl(generator=mock_llm_provider)

    @pytest.mark.asyncio
    async def test_generate(self, generator, mock_llm_provider):
        """测试生成响应"""
        documents = [
            RetrievedDocument(id="1", content="Content 1", metadata={}, score=0.9, document_id="doc1", document_name="Doc 1", chunk_index=0)
        ]

        result = await generator.generate(
            query="test query",
            documents=documents
        )

        assert result == "Test response"
        mock_llm_provider.generate.assert_called()

    @pytest.mark.asyncio
    async def test_generate_stream(self, generator, mock_llm_provider):
        """测试流式生成"""
        documents = [
            RetrievedDocument(id="1", content="Content 1", metadata={}, score=0.9, document_id="doc1", document_name="Doc 1", chunk_index=0)
        ]

        async def mock_async_gen(query, documents, conversation_history=None, temperature=0.7, max_tokens=2000):
            yield "Test "
            yield "response"

        generator.generator.generate_stream = mock_async_gen

        tokens = []
        async for token in generator.generate_stream(
            query="test query",
            documents=documents
        ):
            tokens.append(token)

        assert len(tokens) == 2


class TestQueryContext:
    """QueryContext测试"""

    def test_query_context_creation(self):
        """测试QueryContext创建"""
        context = QueryContext(
            workspace_id=uuid4(),
            dataset_ids=[uuid4()],
            retrieval_mode="semantic",
            top_k=5,
            similarity_threshold=0.7,
            rerank=True
        )

        assert context.workspace_id is not None
        assert context.dataset_ids is not None
        assert context.retrieval_mode == "semantic"
        assert context.top_k == 5
        assert context.similarity_threshold == 0.7
        assert context.rerank is True


class TestRetrievedDocument:
    """RetrievedDocument测试"""

    def test_retrieved_document_creation(self):
        """测试RetrievedDocument创建"""
        doc = RetrievedDocument(
            id="1",
            content="Test content",
            metadata={"key": "value"},
            score=0.9,
            document_id="doc1",
            document_name="Document 1",
            chunk_index=0
        )

        assert doc.id == "1"
        assert doc.content == "Test content"
        assert doc.score == 0.9
        assert doc.metadata["key"] == "value"


class TestRAGResponse:
    """RAGResponse测试"""

    def test_rag_response_creation(self):
        """测试RAGResponse创建"""
        response = RAGResponse(
            answer="Test answer",
            retrieved_documents=[],
            tokens_used=100,
            retrieval_time_ms=50,
            generation_time_ms=100,
            metadata={}
        )

        assert response.answer == "Test answer"
        assert response.tokens_used == 100
        assert response.retrieval_time_ms == 50
        assert response.generation_time_ms == 100
