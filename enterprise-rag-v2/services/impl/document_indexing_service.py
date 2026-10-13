"""
文档索引服务

提供文档向量化索引功能，支持重试机制和错误处理
"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from uuid import UUID

from core.rag.vector_store import QdrantVectorStore, VectorStore, create_vector_store
from core.rag.embedding import EmbeddingService
from core.rag.document_processor import DocumentProcessor
from core.rag.collection_manager import CollectionManager
from core.rag_config import get_rag_config
from infrastructure.database.models import Document, DocumentChunk, DocumentStatus
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class RetryConfig:
    """重试配置"""
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    RETRY_BACKOFF = 2.0


class DocumentIndexingService:
    """
    文档索引服务
    
    职责：
    1. 文档文本提取
    2. 文本分块
    3. 向量嵌入生成
    4. 向量存储索引
    5. 错误处理和重试
    """
    
    def __init__(
        self,
        session: AsyncSession,
        vector_store: Optional[VectorStore] = None,
        embedding_service: Optional[EmbeddingService] = None,
        document_processor: Optional[DocumentProcessor] = None
    ):
        self.session = session
        self.config = get_rag_config()
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._document_processor = document_processor
    
    @property
    def vector_store(self) -> VectorStore:
        """获取向量存储实例"""
        if self._vector_store is None:
            self._vector_store = QdrantVectorStore()
        return self._vector_store
    
    @property
    def embedding_service(self) -> EmbeddingService:
        """获取嵌入服务实例"""
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
        return self._embedding_service
    
    @property
    def document_processor(self) -> DocumentProcessor:
        """获取文档处理器实例"""
        if self._document_processor is None:
            self._document_processor = DocumentProcessor()
        return self._document_processor
    
    async def index_document(
        self,
        document_id: UUID,
        workspace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        索引文档
        
        Args:
            document_id: 文档ID
            workspace_id: 工作空间ID（用于集合隔离）
            
        Returns:
            Dict: 索引结果
        """
        logger.info(f"Starting to index document {document_id}")
        
        result = {
            "document_id": str(document_id),
            "status": "pending",
            "chunks_created": 0,
            "vectors_stored": 0,
            "errors": []
        }
        
        try:
            # 1. 获取文档
            document = await self._get_document(document_id)
            if not document:
                result["errors"].append("Document not found")
                return result
            
            # 2. 更新状态为处理中
            await self._update_document_status(document_id, DocumentStatus.PROCESSING)
            
            # 3. 确保集合存在（与查询链路保持同一向量存储实现）
            vector_store = await self._get_vector_store(workspace_id)
            if not await vector_store.collection_exists():
                if not await vector_store.create_collection():
                    raise RuntimeError("Failed to ensure collection exists")
            
            # 4. 提取文本
            text = await self._extract_text_with_retry(document)
            if not text:
                raise RuntimeError("Failed to extract text from document")
            
            # 5. 分块文本
            chunks = await self._split_text_with_retry(text, str(document_id))
            result["chunks_created"] = len(chunks)
            
            # 6. 保存分块到数据库
            await self._save_chunks(document_id, chunks)
            
            # 7. 生成向量并存储
            vectors_stored = await self._index_chunks_with_retry(
                chunks, 
                str(document_id),
                str(document.dataset_id),
                workspace_id
            )
            result["vectors_stored"] = vectors_stored
            
            # 8. 更新状态为完成
            await self._update_document_status(
                document_id, 
                DocumentStatus.COMPLETED,
                chunk_count=len(chunks)
            )
            
            result["status"] = "completed"
            logger.info(f"Successfully indexed document {document_id}")
            
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError, OSError, AttributeError) as e:
            logger.error(f"Failed to index document {document_id}: {e}")
            result["status"] = "failed"
            result["errors"].append(str(e))
            
            await self._update_document_status(
                document_id,
                DocumentStatus.FAILED,
                error=str(e)
            )
        
        return result
    
    async def _get_document(self, document_id: UUID) -> Optional[Document]:
        """获取文档"""
        result = await self.session.execute(
            select(Document).where(Document.id == document_id)
        )
        return result.scalar_one_or_none()
    
    async def _update_document_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        chunk_count: Optional[int] = None,
        error: Optional[str] = None
    ) -> None:
        """更新文档状态"""
        update_data = {"status": status, "updated_at": datetime.now(timezone.utc)}
        
        if chunk_count is not None:
            update_data["chunk_count"] = chunk_count
        
        if error:
            update_data["error_message"] = error
        
        await self.session.execute(
            update(Document)
            .where(Document.id == document_id)
            .values(**update_data)
        )
        await self.session.flush()
    
    async def _get_collection_manager(
        self,
        workspace_id: Optional[str] = None
    ) -> CollectionManager:
        """获取集合管理器"""
        if workspace_id:
            collection_name = CollectionManager.get_workspace_collection_name(workspace_id)
            return await CollectionManager.get_instance(collection_name)
        return await CollectionManager.get_instance()

    async def _get_vector_store(self, workspace_id: Optional[str] = None) -> VectorStore:
        """获取向量存储实例（与 chat 查询侧统一）"""
        if workspace_id:
            collection_name = CollectionManager.get_workspace_collection_name(workspace_id)
        else:
            collection_name = get_rag_config().collection_name

        return await create_vector_store(
            collection_name=collection_name,
            embedding_service=self.embedding_service,
            use_memory_fallback=True
        )
    
    async def _extract_text_with_retry(self, document: Document) -> Optional[str]:
        """带重试的文本提取"""
        for attempt in range(RetryConfig.MAX_RETRIES):
            try:
                text = await self.document_processor.extract_text(
                    document.file_path,
                    document.file_type
                )
                return text
            except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as e:
                logger.warning(f"Text extraction attempt {attempt + 1} failed: {e}")
                if attempt < RetryConfig.MAX_RETRIES - 1:
                    delay = RetryConfig.RETRY_DELAY * (RetryConfig.RETRY_BACKOFF ** attempt)
                    await asyncio.sleep(delay)
        
        return None
    
    async def _split_text_with_retry(
        self,
        text: str,
        document_id: str
    ) -> List[Dict[str, Any]]:
        """带重试的文本分块"""
        for attempt in range(RetryConfig.MAX_RETRIES):
            try:
                chunks = self.document_processor.create_chunks(
                    text,
                    document_id,
                    metadata={"document_id": document_id}
                )
                return chunks
            except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as e:
                logger.warning(f"Text splitting attempt {attempt + 1} failed: {e}")
                if attempt < RetryConfig.MAX_RETRIES - 1:
                    delay = RetryConfig.RETRY_DELAY * (RetryConfig.RETRY_BACKOFF ** attempt)
                    await asyncio.sleep(delay)
        
        return []
    
    async def _save_chunks(
        self,
        document_id: UUID,
        chunks: List[Dict[str, Any]]
    ) -> None:
        """保存分块到数据库"""
        for chunk_data in chunks:
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=chunk_data["chunk_index"],
                content=chunk_data["content"],
                metadata=chunk_data.get("metadata", {})
            )
            self.session.add(chunk)
        
        await self.session.flush()
    
    async def _index_chunks_with_retry(
        self,
        chunks: List[Dict[str, Any]],
        document_id: str,
        dataset_id: str,
        workspace_id: Optional[str] = None
    ) -> int:
        """带重试的向量索引"""
        vectors_stored = 0

        # 先获取文档信息以获取 document_name
        document = await self._get_document(UUID(document_id))
        document_name = document.file_name if document else "未知文档"

        # 使用正确的 workspace collection name
        from core.rag.collection_manager import CollectionManager
        if workspace_id:
            collection_name = CollectionManager.get_workspace_collection_name(workspace_id)
        else:
            collection_name = get_rag_config().collection_name

        logger.info(f"索引文档使用 collection: {collection_name}, workspace_id: {workspace_id}, document_name: {document_name}")

        vector_store = await create_vector_store(
            collection_name=collection_name,
            embedding_service=self.embedding_service,
            use_memory_fallback=True
        )

        for chunk in chunks:
            for attempt in range(RetryConfig.MAX_RETRIES):
                try:
                    # 生成向量
                    vector = await self.embedding_service.embed_text(chunk["content"])

                    # 构建向量点
                    point = {
                        "id": chunk["id"],
                        "vector": vector,
                        "payload": {
                            "document_id": document_id,
                            "document_name": document_name,
                            "dataset_id": dataset_id,
                            "chunk_index": chunk["chunk_index"],
                            "content": chunk["content"][:1000],
                            "workspace_id": workspace_id or "default"
                        }
                    }

                    # 存储向量
                    success = await vector_store.upsert([point])
                    
                    if success:
                        vectors_stored += 1
                        break
                    else:
                        raise RuntimeError("Vector upsert failed")
                        
                except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as e:
                    logger.warning(
                        f"Vector indexing attempt {attempt + 1} failed for chunk {chunk['id']}: {e}"
                    )
                    if attempt < RetryConfig.MAX_RETRIES - 1:
                        delay = RetryConfig.RETRY_DELAY * (RetryConfig.RETRY_BACKOFF ** attempt)
                        await asyncio.sleep(delay)
        
        return vectors_stored
    
    async def delete_document_vectors(
        self,
        document_id: UUID,
        workspace_id: Optional[str] = None
    ) -> bool:
        """
        删除文档向量
        
        Args:
            document_id: 文档ID
            workspace_id: 工作空间ID
            
        Returns:
            bool: 是否成功
        """
        try:
            # 获取所有分块ID
            result = await self.session.execute(
                select(DocumentChunk.id).where(DocumentChunk.document_id == document_id)
            )
            chunk_ids = [str(row[0]) for row in result.fetchall()]

            if chunk_ids:
                # 使用正确的 workspace collection name
                from core.rag.collection_manager import CollectionManager
                if workspace_id:
                    collection_name = CollectionManager.get_workspace_collection_name(workspace_id)
                else:
                    collection_name = get_rag_config().collection_name

                vector_store = QdrantVectorStore(collection_name=collection_name)

                # 删除向量
                success = await vector_store.delete(chunk_ids)
                return success
            
            return True
            
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError, OSError, AttributeError) as e:
            logger.error(f"Failed to delete document vectors: {e}")
            return False
    
    async def batch_index_documents(
        self,
        document_ids: List[UUID],
        workspace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        批量索引文档
        
        Args:
            document_ids: 文档ID列表
            workspace_id: 工作空间ID
            
        Returns:
            Dict: 批量索引结果
        """
        results = {
            "total": len(document_ids),
            "successful": 0,
            "failed": 0,
            "details": []
        }
        
        for doc_id in document_ids:
            result = await self.index_document(doc_id, workspace_id)
            results["details"].append(result)
            
            if result["status"] == "completed":
                results["successful"] += 1
            else:
                results["failed"] += 1
        
        return results
