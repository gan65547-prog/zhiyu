"""
DocumentRepository单元测试
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from infrastructure.repositories.document_repository import (
    DocumentRepositoryImpl,
    DocumentChunkRepositoryImpl
)
from infrastructure.database.models import Document, DocumentChunk, DocumentType, DocumentStatus
from core.value_objects.pagination import Pagination


class MockSession:
    def __init__(self):
        self.added = []
        self.flushed = False
        self.refreshed = []
        self.queries = []

    def add(self, entity):
        self.added.append(entity)

    async def flush(self):
        self.flushed = True

    async def refresh(self, entity):
        self.refreshed.append(entity)

    async def execute(self, query):
        self.queries.append(query)
        return MockResult()


class MockResult:
    def __init__(self, rowcount=1):
        self._rowcount = rowcount

    @property
    def rowcount(self):
        return self._rowcount

    def scalars(self):
        return MockScalars([])

    def scalar_one(self):
        return 0

    def scalar_one_or_none(self):
        return None


class MockScalars:
    def __init__(self, data):
        self._data = data

    def all(self):
        return self._data

    def one_or_none(self):
        return self._data[0] if self._data else None


class TestDocumentRepository:
    """DocumentRepository测试"""

    @pytest.fixture
    def mock_session(self):
        return MockSession()

    @pytest.fixture
    def repo(self, mock_session):
        return DocumentRepositoryImpl(mock_session)

    @pytest.fixture
    def sample_doc_id(self):
        return uuid4()

    @pytest.fixture
    def sample_dataset_id(self):
        return uuid4()

    @pytest.fixture
    def sample_chunk_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_document(self, repo, mock_session):
        """测试创建文档"""
        doc = Document(
            id=uuid4(),
            dataset_id=uuid4(),
            file_name="test.pdf",
            file_type=DocumentType.PDF,
            file_size=1024,
            file_path="/uploads/test.pdf",
            status=DocumentStatus.PENDING,
            tags=[],
            metadata={}
        )

        result = await repo.create(doc)

        assert doc in mock_session.added
        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo, sample_doc_id):
        """测试根据ID获取"""
        result = await repo.get_by_id(sample_doc_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_dataset(self, repo, sample_dataset_id):
        """测试获取数据集下的文档"""
        result = await repo.get_by_dataset(sample_dataset_id)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_update_document(self, repo, mock_session):
        """测试更新文档"""
        doc = Document(
            id=uuid4(),
            dataset_id=uuid4(),
            file_name="test.pdf",
            file_type=DocumentType.PDF,
            file_size=1024,
            file_path="/uploads/test.pdf",
            status=DocumentStatus.PENDING,
            tags=[],
            metadata={}
        )

        result = await repo.update(doc)

        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_delete_document(self, repo, mock_session, sample_doc_id):
        """测试删除文档"""
        result = await repo.delete(sample_doc_id)

        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_exists_document(self, repo, sample_doc_id):
        """测试检查文档存在"""
        result = await repo.exists(sample_doc_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_list_supports_keyword_filter(self, repo, mock_session, sample_dataset_id):
        """文档列表关键词必须同时作用于总数和分页查询。"""
        await repo.list(
            {"dataset_id": sample_dataset_id, "keyword": "回归素材"},
            Pagination(page=1, page_size=20),
        )
        assert len(mock_session.queries) == 2
        assert all("file_name" in str(query) for query in mock_session.queries)


class TestDocumentChunkRepository:
    """DocumentChunkRepository测试"""

    @pytest.fixture
    def mock_session(self):
        return MockSession()

    @pytest.fixture
    def repo(self, mock_session):
        return DocumentChunkRepositoryImpl(mock_session)

    @pytest.fixture
    def sample_doc_id(self):
        return uuid4()

    @pytest.fixture
    def sample_chunk_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_chunk(self, repo, mock_session):
        """测试创建文档块"""
        chunk = DocumentChunk(
            id=uuid4(),
            document_id=uuid4(),
            content="Test content",
            chunk_index=0,
            metadata={}
        )

        result = await repo.create(chunk)

        assert chunk in mock_session.added
        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo, sample_chunk_id):
        """测试根据ID获取"""
        result = await repo.get_by_id(sample_chunk_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_document(self, repo, sample_doc_id):
        """测试获取文档下的块"""
        result = await repo.get_by_document(sample_doc_id)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_count_by_document(self, repo, sample_doc_id):
        """测试统计文档块数量"""
        result = await repo.count_by_document(sample_doc_id)
        assert result == 0

    @pytest.mark.asyncio
    async def test_update_chunk(self, repo, mock_session):
        """测试更新文档块"""
        chunk = DocumentChunk(
            id=uuid4(),
            document_id=uuid4(),
            content="Original",
            chunk_index=0,
            metadata={}
        )

        result = await repo.update(chunk)

        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_delete_chunk(self, repo, mock_session, sample_chunk_id):
        """测试删除文档块"""
        result = await repo.delete(sample_chunk_id)

        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_exists_chunk(self, repo, sample_chunk_id):
        """测试检查文档块存在"""
        result = await repo.exists(sample_chunk_id)
        assert result is False
