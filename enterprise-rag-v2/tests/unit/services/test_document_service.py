"""
DocumentService单元测试
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.impl.document_service import DocumentServiceImpl
from infrastructure.database.models import Document, DocumentStatus, DocumentType
from core.value_objects.pagination import Pagination, Page


class MockDocumentRepo:
    """模拟文档Repository"""
    def __init__(self):
        self.documents = {}

    async def get_by_id(self, doc_id):
        if doc_id in self.documents:
            return self.documents[doc_id]
        sid = str(doc_id)
        for k, v in self.documents.items():
            if str(k) == sid:
                return v
        return None

    async def create(self, document):
        if not document.id:
            document.id = uuid4()
        if not document.created_at:
            document.created_at = datetime.utcnow()
        if not document.updated_at:
            document.updated_at = datetime.utcnow()
        self.documents[document.id] = document
        return document

    async def update(self, document):
        if not document.updated_at:
            document.updated_at = datetime.utcnow()
        self.documents[document.id] = document
        return document

    async def delete(self, doc_id):
        sid = str(doc_id)
        for k in list(self.documents.keys()):
            if str(k) == sid:
                del self.documents[k]
                return True
        return False

    async def batch_delete(self, doc_ids):
        deleted = 0
        for doc_id in doc_ids:
            if doc_id in self.documents:
                del self.documents[doc_id]
                deleted += 1
        return deleted

    async def list(self, filters=None, pagination=None):
        items = list(self.documents.values())

        if filters:
            if "dataset_id" in filters:
                items = [d for d in items if d.dataset_id == filters["dataset_id"]]
            if "status" in filters:
                items = [d for d in items if d.status.value == filters["status"] if hasattr(d.status, 'value')]

        total = len(items)
        page = pagination.page if pagination else 1
        page_size = pagination.page_size if pagination else 20
        start = (page - 1) * page_size
        end = start + page_size

        return MagicMock(items=items[start:end], total=total, page=page, page_size=page_size)

    async def get_by_dataset_and_name(self, dataset_id, file_name):
        for d in self.documents.values():
            if str(d.dataset_id) == str(dataset_id) and d.file_name == file_name:
                return d
        return None


class MockChunkRepo:
    """模拟Chunk Repository"""
    def __init__(self):
        self.chunks = {}

    async def create(self, chunk):
        if not chunk.id:
            chunk.id = uuid4()
        self.chunks[chunk.id] = chunk
        return chunk


class TestDocumentService:
    """DocumentService测试"""

    @pytest.fixture
    def mock_session(self):
        """创建模拟数据库会话"""
        session = MagicMock()
        result = MagicMock()
        result.all.return_value = []
        result.scalars.return_value.all.return_value = []
        result.scalar_one.return_value = 0
        result.scalar_one_or_none.return_value = None
        ds = MagicMock()
        ws = MagicMock()
        ws.tenant_id = "t1"
        result.first.return_value = (ds, ws)
        session.execute = AsyncMock(return_value=result)
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.add = MagicMock()
        session.get = AsyncMock(return_value=None)
        return session

    @pytest.fixture
    def document_service(self, mock_session):
        """创建DocumentServiceImpl实例"""
        service = DocumentServiceImpl(session=mock_session)
        service.document_repo = MockDocumentRepo()
        service.chunk_repo = MockChunkRepo()
        return service

    @pytest.fixture
    def sample_document_id(self):
        return uuid4()

    @pytest.fixture
    def sample_dataset_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_upload_document_success(self, document_service, sample_dataset_id):
        """测试上传文档成功"""
        result = await document_service.upload_document(
            dataset_id=sample_dataset_id,
            file_path="/uploads/test.pdf",
            file_name="test.pdf",
            file_type="pdf",
            file_size=1024,
            tags=["test"],
            metadata={"author": "test"}
        )

        assert result["file_name"] == "test.pdf"
        assert result["file_type"] == "pdf"
        assert result["file_size"] == 1024
        assert result["status"] == "pending"
        assert result["tags"] == ["test"]

    @pytest.mark.asyncio
    async def test_upload_document_various_types(self, document_service, sample_dataset_id):
        """测试上传各种类型文档"""
        file_types = ["pdf", "PDF", ".pdf", "docx", "DOCX", "txt", "TXT", "md", "MD", "html", "HTML"]

        for file_type in file_types:
            result = await document_service.upload_document(
                dataset_id=sample_dataset_id,
                file_path=f"/uploads/test.{file_type}",
                file_name=f"test.{file_type}",
                file_type=file_type,
                file_size=1024
            )
            assert result["file_type"] in ["pdf", "docx", "txt", "md", "html"]

    @pytest.mark.asyncio
    async def test_get_document_success(self, document_service, sample_dataset_id):
        """测试获取文档详情"""
        doc_id = uuid4()
        doc = Document(
            id=doc_id,
            dataset_id=sample_dataset_id,
            file_name="test.pdf",
            file_type=DocumentType.PDF,
            file_size=1024,
            file_path="/uploads/test.pdf",
            status=DocumentStatus.COMPLETED,
            tags=["test"],
            metadata={},
            chunk_count=5,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        document_service.document_repo.documents[doc_id] = doc

        result = await document_service.get_document(doc_id)

        assert result is not None
        assert result["file_name"] == "test.pdf"
        assert result["chunk_count"] == 5

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, document_service, sample_document_id):
        """测试获取不存在的文档"""
        result = await document_service.get_document(sample_document_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_document_success(self, document_service, sample_dataset_id):
        """测试更新文档"""
        doc_id = uuid4()
        doc = Document(
            id=doc_id,
            dataset_id=sample_dataset_id,
            file_name="old_name.pdf",
            file_type=DocumentType.PDF,
            file_size=1024,
            file_path="/uploads/old.pdf",
            status=DocumentStatus.PENDING,
            tags=["old"],
            metadata={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        document_service.document_repo.documents[doc_id] = doc

        result = await document_service.update_document(
            document_id=doc_id,
            file_name="new_name.pdf",
            tags=["new", "updated"],
            metadata={"key": "value"}
        )

        assert result["file_name"] == "new_name.pdf"
        assert result["tags"] == ["new", "updated"]
        assert result["metadata"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_update_document_not_found(self, document_service, sample_document_id):
        """测试更新不存在的文档"""
        with pytest.raises(ValueError, match="文档不存在"):
            await document_service.update_document(
                document_id=sample_document_id,
                file_name="new_name.pdf"
            )

    @pytest.mark.asyncio
    async def test_delete_document_success(self, document_service, sample_dataset_id):
        """测试删除文档"""
        doc_id = uuid4()
        doc = Document(
            id=doc_id,
            dataset_id=sample_dataset_id,
            file_name="to_delete.pdf",
            file_type=DocumentType.PDF,
            file_size=1024,
            file_path="/uploads/delete.pdf",
            status=DocumentStatus.PENDING,
            tags=[],
            metadata={}
        )
        document_service.document_repo.documents[doc_id] = doc

        result = await document_service.delete_document(doc_id)

        assert result is True
        assert doc_id not in document_service.document_repo.documents

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, document_service, sample_document_id):
        """测试删除不存在的文档"""
        result = await document_service.delete_document(sample_document_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_batch_delete_documents(self, document_service, sample_dataset_id):
        """测试批量删除文档"""
        doc_ids = [uuid4() for _ in range(3)]

        for doc_id in doc_ids:
            doc = Document(
                id=doc_id,
                dataset_id=sample_dataset_id,
                file_name=f"doc_{doc_id}.pdf",
                file_type=DocumentType.PDF,
                file_size=1024,
                file_path=f"/uploads/doc_{doc_id}.pdf",
                status=DocumentStatus.PENDING,
                tags=[],
                metadata={}
            )
            document_service.document_repo.documents[doc_id] = doc

        result = await document_service.batch_delete_documents(doc_ids)

        assert result["deleted_count"] == 3
        assert result["total"] == 3
        for doc_id in doc_ids:
            assert doc_id not in document_service.document_repo.documents

    @pytest.mark.asyncio
    async def test_list_documents_empty(self, document_service, sample_dataset_id):
        """测试查询空文档列表"""
        result = await document_service.list_documents(dataset_id=sample_dataset_id)

        assert result.total == 0
        assert len(result.items) == 0

    @pytest.mark.asyncio
    async def test_list_documents_with_data(self, document_service, sample_dataset_id):
        """测试查询文档列表"""
        for i in range(5):
            doc_id = uuid4()
            doc = Document(
                id=doc_id,
                dataset_id=sample_dataset_id,
                file_name=f"doc_{i}.pdf",
                file_type=DocumentType.PDF,
                file_size=1024 * (i + 1),
                file_path=f"/uploads/doc_{i}.pdf",
                status=DocumentStatus.COMPLETED if i % 2 == 0 else DocumentStatus.PENDING,
                tags=[],
                metadata={},
                chunk_count=i,
                created_at=datetime.utcnow()
            )
            document_service.document_repo.documents[doc_id] = doc

        result = await document_service.list_documents(dataset_id=sample_dataset_id)

        assert result.total == 5
        assert len(result.items) == 5

    @pytest.mark.asyncio
    async def test_list_documents_with_pagination(self, document_service, sample_dataset_id):
        """测试带分页的文档列表"""
        for i in range(25):
            doc_id = uuid4()
            doc = Document(
                id=doc_id,
                dataset_id=sample_dataset_id,
                file_name=f"doc_{i}.pdf",
                file_type=DocumentType.PDF,
                file_size=1024,
                file_path=f"/uploads/doc_{i}.pdf",
                status=DocumentStatus.COMPLETED,
                tags=[],
                metadata={},
                chunk_count=i,
                created_at=datetime.utcnow()
            )
            document_service.document_repo.documents[doc_id] = doc

        pagination = Pagination(page=2, page_size=10)
        result = await document_service.list_documents(
            dataset_id=sample_dataset_id,
            pagination=pagination
        )

        assert result.total == 25
        assert len(result.items) == 10
        assert result.page == 2
        assert result.page_size == 10

    @pytest.mark.asyncio
    async def test_list_documents_with_status_filter(self, document_service, sample_dataset_id):
        """测试按状态筛选文档"""
        for i in range(6):
            doc_id = uuid4()
            status = DocumentStatus.COMPLETED if i < 3 else DocumentStatus.PENDING
            doc = Document(
                id=doc_id,
                dataset_id=sample_dataset_id,
                file_name=f"doc_{i}.pdf",
                file_type=DocumentType.PDF,
                file_size=1024,
                file_path=f"/uploads/doc_{i}.pdf",
                status=status,
                tags=[],
                metadata={},
                created_at=datetime.utcnow()
            )
            document_service.document_repo.documents[doc_id] = doc

        result = await document_service.list_documents(
            dataset_id=sample_dataset_id,
            status="completed"
        )

        assert result.total == 3

    @pytest.mark.asyncio
    async def test_reindex_document_success(self, document_service, sample_dataset_id):
        """测试重新索引文档"""
        doc_id = uuid4()
        doc = Document(
            id=doc_id,
            dataset_id=sample_dataset_id,
            file_name="test.pdf",
            file_type=DocumentType.PDF,
            file_size=1024,
            file_path="/uploads/test.pdf",
            status=DocumentStatus.COMPLETED,
            tags=[],
            metadata={}
        )
        document_service.document_repo.documents[doc_id] = doc

        result = await document_service.reindex_document(doc_id)

        assert result["document_id"] == str(doc_id)
        assert result["status"] == "pending"
        assert "重新索引队列" in result["message"]

    @pytest.mark.asyncio
    async def test_reindex_document_not_found(self, document_service, sample_document_id):
        """测试重新索引不存在的文档"""
        with pytest.raises(ValueError, match="文档不存在"):
            await document_service.reindex_document(sample_document_id)

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="process_document 依赖真实文件、AsyncSessionLocal 进度会话与向量索引；由集成测试覆盖")
    async def test_process_document_success(self, document_service, sample_dataset_id):
        """测试处理文档（重逻辑见集成测试）"""
        doc_id = uuid4()
        doc = Document(
            id=doc_id,
            dataset_id=sample_dataset_id,
            file_name="test.pdf",
            file_type=DocumentType.PDF,
            file_size=1024,
            file_path="/uploads/test.pdf",
            status=DocumentStatus.PENDING,
            tags=[],
            metadata={}
        )
        document_service.document_repo.documents[doc_id] = doc

        result = await document_service.process_document(doc_id)

        assert result is True
        assert doc.status == DocumentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_process_document_not_found(self, document_service, sample_document_id):
        """测试处理不存在的文档"""
        result = await document_service.process_document(sample_document_id)
        assert result is False

    def test_normalize_file_type(self, document_service):
        """测试文件类型标准化"""
        assert document_service._normalize_file_type("pdf") == DocumentType.PDF
        assert document_service._normalize_file_type("PDF") == DocumentType.PDF
        assert document_service._normalize_file_type(".pdf") == DocumentType.PDF
        assert document_service._normalize_file_type("docx") == DocumentType.DOCX
        assert document_service._normalize_file_type("DOCX") == DocumentType.DOCX
        assert document_service._normalize_file_type("word") == DocumentType.DOCX
        assert document_service._normalize_file_type("txt") == DocumentType.TXT
        assert document_service._normalize_file_type("text") == DocumentType.TXT
        assert document_service._normalize_file_type("md") == DocumentType.MD
        assert document_service._normalize_file_type("markdown") == DocumentType.MD
        assert document_service._normalize_file_type("html") == DocumentType.HTML
        assert document_service._normalize_file_type("htm") == DocumentType.HTML
        assert document_service._normalize_file_type("unknown") == DocumentType.TXT
