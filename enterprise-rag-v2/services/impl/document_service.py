"""
文档服务实现
"""

from datetime import datetime, timezone
from time import monotonic
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, insert
from sqlalchemy.exc import SQLAlchemyError

from infrastructure.database.models import Document, DocumentChunk, DocumentStatus, DocumentType, Dataset
from infrastructure.repositories.document_repository import (
    DocumentRepositoryImpl,
    DocumentChunkRepositoryImpl
)
from infrastructure.repositories.dataset_repository import DatasetRepositoryImpl
from infrastructure.database.session import AsyncSessionLocal
from services.interfaces.document_service import DocumentService
from core.value_objects.pagination import Pagination, Page
from infrastructure.logging.logger import get_logger

logger = get_logger("services.impl.document_service")


class DocumentServiceImpl(DocumentService):
    """文档服务实现"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.document_repo = DocumentRepositoryImpl(session)
        self.chunk_repo = DocumentChunkRepositoryImpl(session)
        self.dataset_repo = DatasetRepositoryImpl(session)
        self._project_root = Path(__file__).resolve().parents[2]

    def _resolve_source_path(self, file_path: str) -> Path:
        """将数据库中的文件路径解析为可访问的绝对路径。"""
        source_path = Path(file_path)
        if source_path.is_absolute():
            return source_path

        # 兼容不同运行目录（API/Celery/脚本）
        candidate_paths = [
            Path.cwd() / source_path,
            self._project_root / source_path,
        ]
        for candidate in candidate_paths:
            if candidate.exists():
                return candidate
        # 都不存在时，返回默认候选路径供上层报错/日志使用
        return candidate_paths[0]

    async def get_dataset_document_counts(self, dataset_id: UUID) -> dict:
        """按处理状态统计数据集文档数量，供问答就绪度端点使用。"""
        result = await self.session.execute(
            select(Document.status, func.count(Document.id))
            .where(Document.dataset_id == str(dataset_id))
            .group_by(Document.status)
        )
        status_counts: dict[str, int] = {}
        for status_value, total in result.all():
            key = str(getattr(status_value, "value", status_value)).lower()
            status_counts[key] = int(total)
        return {
            "completed": status_counts.get(DocumentStatus.COMPLETED.value, 0),
            "processing": status_counts.get(DocumentStatus.PENDING.value, 0)
            + status_counts.get(DocumentStatus.PROCESSING.value, 0),
            "failed": status_counts.get(DocumentStatus.FAILED.value, 0),
        }

    async def upload_document(
        self,
        dataset_id: UUID,
        file_path: str,
        file_name: str,
        file_type: str,
        file_size: int,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        knowledge_type: Optional[str] = None,
    ) -> dict:
        """上传文档"""
        doc_type = self._normalize_file_type(file_type)

        # 标准化 knowledge_type
        kt = None
        if knowledge_type:
            kt = self._normalize_knowledge_type(knowledge_type)

        # 将UUID转换为字符串格式（数据库中存储的是字符串）
        dataset_id_str = str(dataset_id) if hasattr(dataset_id, 'hex') else dataset_id

        # 检查是否存在同名文件
        existing_doc = await self.document_repo.get_by_dataset_and_name(dataset_id_str, file_name)
        if existing_doc:
            raise ValueError(f"文件 '{file_name}' 已经存在于该数据集中")

        # 获取租户ID并检查配额
        from infrastructure.database.models import Dataset, Workspace
        from sqlalchemy import select

        # 获取数据集和工作空间信息
        result = await self.session.execute(
            select(Dataset, Workspace)
            .join(Workspace, Dataset.workspace_id == Workspace.id)
            .where(Dataset.id == dataset_id_str)
        )
        row = result.first()

        if not row:
            raise ValueError(f"数据集 {dataset_id} 不存在")

        dataset, workspace = row
        tenant_id = workspace.tenant_id

        # 暂时移除配额检查，专注于修复文件上传功能
        # 后续可以重新添加配额检查逻辑

        # 存绝对路径，避免服务工作目录变化导致后续无法读取原文
        normalized_file_path = str(Path(file_path).resolve())
        document = Document(
            dataset_id=dataset_id_str,
            file_name=file_name,
            file_type=doc_type,
            file_size=file_size,
            file_path=normalized_file_path,
            status=DocumentStatus.PENDING,
            knowledge_type=kt,
            tags=tags or [],
            metadata=metadata or {}
        )

        created = await self.document_repo.create(document)

        # 暂时移除配额使用量增加，专注于修复文件上传功能
        # 后续可以重新添加配额使用量增加逻辑

        return {
            "id": str(created.id),
            "dataset_id": str(created.dataset_id),
            "file_name": created.file_name,
            "file_type": created.file_type.value if hasattr(created.file_type, 'value') else created.file_type,
            "file_size": created.file_size,
            "file_path": created.file_path,
            "status": created.status.value if hasattr(created.status, 'value') else created.status,
            "knowledge_type": created.knowledge_type.value if created.knowledge_type and hasattr(created.knowledge_type, 'value') else created.knowledge_type,
            "tags": created.tags,
            "metadata": created.metadata,
            "chunk_count": created.chunk_count,
            "created_at": created.created_at.isoformat() if created.created_at else None
        }

    async def get_document(self, document_id: UUID) -> Optional[dict]:
        """获取文档详情"""
        document = await self.document_repo.get_by_id(document_id)
        if not document:
            return None

        # 避免 ORM 代理对象在序列化时触发递归
        safe_tags = list(document.tags or []) if isinstance(document.tags, list) else []
        safe_metadata = dict(document.metadata or {}) if isinstance(document.metadata, dict) else {}

        return {
            "id": str(document.id),
            "dataset_id": str(document.dataset_id),
            "file_name": document.file_name,
            "file_type": document.file_type.value if hasattr(document.file_type, 'value') else document.file_type,
            "file_size": document.file_size,
            "file_path": document.file_path,
            "status": document.status.value if hasattr(document.status, 'value') else document.status,
            "knowledge_type": document.knowledge_type.value if document.knowledge_type and hasattr(document.knowledge_type, 'value') else document.knowledge_type,
            "tags": safe_tags,
            "metadata": safe_metadata,
            "chunk_count": document.chunk_count,
            "indexed_at": document.indexed_at.isoformat() if document.indexed_at else None,
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None
        }

    async def update_document(
        self,
        document_id: UUID,
        file_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        knowledge_type: Optional[str] = None,
    ) -> dict:
        """更新文档"""
        document = await self.document_repo.get_by_id(document_id)
        if not document:
            raise ValueError("文档不存在")

        if file_name is not None:
            document.file_name = file_name
        if tags is not None:
            document.tags = tags
        if metadata is not None:
            document.metadata = metadata
        if knowledge_type is not None:
            document.knowledge_type = self._normalize_knowledge_type(knowledge_type)

        updated = await self.document_repo.update(document)

        return {
            "id": str(updated.id),
            "dataset_id": str(updated.dataset_id),
            "file_name": updated.file_name,
            "file_type": updated.file_type.value if hasattr(updated.file_type, 'value') else updated.file_type,
            "file_size": updated.file_size,
            "status": updated.status.value if hasattr(updated.status, 'value') else updated.status,
            "knowledge_type": updated.knowledge_type.value if updated.knowledge_type and hasattr(updated.knowledge_type, 'value') else updated.knowledge_type,
            "tags": updated.tags,
            "metadata": updated.metadata,
            "chunk_count": updated.chunk_count,
            "created_at": updated.created_at.isoformat() if updated.created_at else None,
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None
        }

    async def delete_document(self, document_id: UUID) -> bool:
        """删除文档"""
        # 将UUID转换为字符串格式（数据库中存储的是字符串）
        document_id_str = str(document_id) if hasattr(document_id, 'hex') else document_id
        document = await self.document_repo.get_by_id(document_id_str)
        if not document:
            return False

        await self.document_repo.delete(document_id_str)
        return True

    async def batch_delete_documents(self, document_ids: List[UUID]) -> Dict[str, Any]:
        """批量删除文档"""
        deleted_count = await self.document_repo.batch_delete(document_ids)

        return {
            "deleted_count": deleted_count,
            "total": len(document_ids)
        }

    async def list_documents(
        self,
        dataset_id: Optional[UUID] = None,
        status: Optional[str] = None,
        file_type: Optional[str] = None,
        knowledge_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        keyword: Optional[str] = None,
        pagination: Optional[Pagination] = None
    ) -> Page:
        """查询文档列表"""
        filters = {}
        if dataset_id:
            filters["dataset_id"] = dataset_id
        if status:
            filters["status"] = status
        if file_type:
            filters["file_type"] = file_type
        if knowledge_type:
            filters["knowledge_type"] = knowledge_type
        if keyword and keyword.strip():
            filters["keyword"] = keyword.strip()

        result = await self.document_repo.list(filters, pagination)

        items = []
        for doc in result.items:
            doc_status = doc.status.value if hasattr(doc.status, 'value') else doc.status
            processing_meta = {}
            if isinstance(doc.extra_metadata, dict):
                processing_meta = doc.extra_metadata.get("processing", {}) or {}
            progress = 0
            if doc_status == "completed":
                progress = 100
            elif doc_status == "processing":
                progress = int(processing_meta.get("progress", 5))
            elif doc_status == "pending":
                progress = int(processing_meta.get("progress", 1))
            elif doc_status == "failed":
                progress = int(processing_meta.get("progress", 0))

            err_raw = processing_meta.get("error_reason")
            error_reason = err_raw.strip() if isinstance(err_raw, str) else None

            items.append({
                "id": str(doc.id),
                "dataset_id": str(doc.dataset_id),
                "name": doc.file_name,
                "type": doc.file_type.value if hasattr(doc.file_type, 'value') else doc.file_type,
                "knowledge_type": doc.knowledge_type.value if doc.knowledge_type and hasattr(doc.knowledge_type, 'value') else doc.knowledge_type,
                "size": doc.file_size,
                "status": doc_status,
                "progress": max(0, min(100, progress)),
                "processing_phase": processing_meta.get("phase"),
                "done_chunks": int(processing_meta.get("done_chunks", 0)),
                "total_chunks": int(processing_meta.get("total_chunks", 0)),
                "tags": doc.tags,
                "segment_count": doc.chunk_count,
                "error_reason": error_reason if doc_status == "failed" else None,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
            })

        return Page(
            items=items,
            total=result.total,
            page=result.page,
            page_size=result.page_size
        )

    async def reindex_document(self, document_id: UUID, force: bool = False) -> dict:
        """重新索引文档"""
        document = await self.document_repo.get_by_id(document_id)
        if not document:
            raise ValueError("文档不存在")

        document.status = DocumentStatus.PENDING
        await self.document_repo.update(document)

        return {
            "document_id": str(document_id),
            "status": "pending",
            "message": "文档已添加到重新索引队列"
        }

    async def get_document_statistics(self, dataset_id: Optional[UUID] = None) -> dict:
        """获取文档统计信息"""
        query = select(func.count()).select_from(Document)
        if dataset_id:
            query = query.where(Document.dataset_id == dataset_id)

        result = await self.session.execute(query)
        total_count = result.scalar_one()

        completed_result = await self.session.execute(
            query.where(Document.status == DocumentStatus.COMPLETED)
        )
        completed_count = completed_result.scalar_one()

        failed_result = await self.session.execute(
            query.where(Document.status == DocumentStatus.FAILED)
        )
        failed_count = failed_result.scalar_one()

        return {
            "total": total_count,
            "completed": completed_count,
            "failed": failed_count,
            "pending": total_count - completed_count - failed_count
        }

    async def process_document(self, document_id: UUID) -> bool:
        """处理文档（提取文本、分块、向量化）"""
        logger.info(f"=========== process_document 被调用，document_id: {document_id} ===========")
        # 将UUID转换为字符串格式
        document_id_str = str(document_id) if hasattr(document_id, 'hex') else document_id
        document = await self.document_repo.get_by_id(document_id_str)
        if not document:
            logger.warning(f"文档不存在: {document_id_str}")
            return False

        try:
            perf_started_at = monotonic()
            stage_started_at = perf_started_at

            def stage_done(stage_name: str, **extra: Any) -> None:
                nonlocal stage_started_at
                now = monotonic()
                elapsed_ms = int((now - stage_started_at) * 1000)
                total_elapsed_ms = int((now - perf_started_at) * 1000)
                kv = " ".join([f"{k}={v}" for k, v in extra.items()])
                suffix = f" {kv}" if kv else ""
                logger.info(
                    f"[文档处理耗时] document_id={document_id_str} stage={stage_name} "
                    f"stage_ms={elapsed_ms} total_ms={total_elapsed_ms}{suffix}"
                )
                stage_started_at = now

            async def update_processing_meta(
                *,
                phase: str,
                progress: int,
                done_chunks: int | None = None,
                total_chunks: int | None = None,
                status: DocumentStatus | None = None,
            ) -> None:
                # 使用主会话更新状态，避免并发冲突
                meta = document.extra_metadata or {}
                processing_meta = meta.get("processing", {})
                processing_meta.update(
                    {
                        "phase": phase,
                        "progress": max(0, min(100, int(progress))),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                if done_chunks is not None:
                    processing_meta["done_chunks"] = int(done_chunks)
                    document.chunk_count = int(done_chunks)
                if total_chunks is not None:
                    processing_meta["total_chunks"] = int(total_chunks)
                if status is not None:
                    document.status = status

                meta["processing"] = processing_meta
                document.extra_metadata = meta
                await self.document_repo.update(document)
                await self.session.commit()

            document.status = DocumentStatus.PROCESSING
            await self.document_repo.update(document)
            # 立即提交「处理中」状态，避免前端轮询期间一直看到 pending。
            await self.session.commit()
            queue_wait_ms = None
            if document.created_at:
                created_at = document.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                queue_wait_ms = int((datetime.now(timezone.utc) - created_at).total_seconds() * 1000)
            logger.info(
                f"[文档处理启动] document_id={document_id_str} file={document.file_name} "
                f"status={document.status.value if hasattr(document.status, 'value') else document.status} "
                f"queue_wait_ms={max(queue_wait_ms or 0, 0)}"
            )
            await update_processing_meta(
                phase="extracting",
                progress=5,
                status=DocumentStatus.PROCESSING,
            )

            # 1. 提取文档文本
            from core.rag.document_processor import DocumentProcessor
            processor = DocumentProcessor()
            
            # 提取真实文本
            text = ""
            if document.file_path:
                # 提前校验文件是否存在，避免进入重型处理后才失败。
                source_path = self._resolve_source_path(document.file_path)
                if not source_path.exists():
                    raise FileNotFoundError(
                        f"源文件不存在: {source_path}"
                    )
                try:
                    text = await processor.extract_text(
                        str(source_path),
                        document.file_type.value if hasattr(document.file_type, 'value') else document.file_type
                    )
                    logger.info(f"提取文本成功，长度: {len(text)}")
                except (ValueError, TypeError, RuntimeError, OSError, AttributeError) as e:
                    logger.error(f"提取文本失败: {e}", exc_info=True)
                    text = ""
            stage_done("extract_text", text_len=len(text))

            # 2. 如果没有提取到文本，抛出错误
            if not text or not text.strip():
                file_type = document.file_type.value if hasattr(document.file_type, "value") else str(document.file_type)
                if str(file_type).lower() in {"image", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}:
                    ocr_status = processor.ocr_runtime_status()
                    if not ocr_status.get("ready"):
                        missing = "、".join(ocr_status.get("missing") or ["OCR 运行时"])
                        raise ValueError(f"图片 OCR 运行时未就绪，缺少：{missing}")
                    raise ValueError(f"图片 OCR 未识别到可索引文字：{document.file_name}")
                raise ValueError(f"无法从文档 {document.file_name} 中提取文本内容")

            # 3. 分块文本
            chunks = processor.create_chunks(
                text=text,
                document_id=str(document.id),
                metadata={
                    "file_name": document.file_name,
                    "file_type": document.file_type.value if hasattr(document.file_type, 'value') else document.file_type,
                    "dataset_id": str(document.dataset_id)
                }
            )
            logger.info(f"分块成功，共 {len(chunks)} 个分段")
            total_chunks = len(chunks)
            stage_done("split_chunks", total_chunks=total_chunks)
            await update_processing_meta(
                phase="chunking",
                progress=20,
                done_chunks=0,
                total_chunks=total_chunks
            )

            # 4. 向量化并存储
            from core.rag.embedding import get_embedding_service
            from core.rag.vector_store import QdrantVectorStore
            from core.rag.collection_manager import CollectionManager

            embedding_service = get_embedding_service()

            # 获取 workspace_id
            dataset = await self.dataset_repo.get_by_id(str(document.dataset_id))
            if not dataset:
                raise ValueError(f"数据集 {document.dataset_id} 不存在")

            workspace_id = str(dataset.workspace_id)
            collection_name = CollectionManager.get_workspace_collection_name(workspace_id)

            logger.info(f"索引文档使用 collection: {collection_name}, workspace_id: {workspace_id}")

            # 使用带 fallback 的向量存储工厂
            from core.rag.vector_store import create_vector_store
            vector_store = await create_vector_store(
                collection_name=collection_name,
                embedding_service=embedding_service,
                use_memory_fallback=True
            )
            await vector_store.create_collection()
            
            # 5. 批量保存分段 + 批量向量化 + 批量写入向量库
            embedding_batch_size = 32
            progress_commit_every_chunks = 25
            progress_commit_every_seconds = 2.0
            vector_points_batch_size = 128
            processed_chunks = 0
            last_progress_commit_at = monotonic()

            chunk_rows: list[dict] = []
            pending_points: list[dict] = []
            upserted_vectors = 0
            embedded_chunks = 0
            embedded_batches = 0

            for batch_start in range(0, total_chunks, embedding_batch_size):
                batch = chunks[batch_start : batch_start + embedding_batch_size]
                texts = [item["content"] for item in batch]
                embeddings: list[list[float] | None] = [None] * len(batch)
                try:
                    embeddings = await embedding_service.embed_batch(texts)
                    embedded_batches += 1
                except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as e:
                    logger.error(
                        f"批量向量化失败，batch_start={batch_start}, size={len(batch)}: {e}",
                        exc_info=True,
                    )

                for offset, chunk_data in enumerate(batch):
                    chunk_id = str(uuid4())
                    chunk_rows.append(
                        {
                            "id": chunk_id,
                            "document_id": str(document.id),
                            "chunk_index": chunk_data["chunk_index"],
                            "content": chunk_data["content"],
                            "extra_metadata": chunk_data["metadata"],
                        }
                    )

                    embedding = embeddings[offset] if offset < len(embeddings) else None
                    if embedding:
                        embedded_chunks += 1
                        pending_points.append(
                            {
                                "id": chunk_id,
                                "vector": embedding,
                                "payload": {
                                    "document_id": str(document.id),
                                    "document_name": document.file_name,
                                    "dataset_id": str(document.dataset_id),
                                    "chunk_index": chunk_data["chunk_index"],
                                    "content": chunk_data["content"],
                                    "metadata": chunk_data["metadata"],
                                },
                            }
                        )

                # 分批 upsert，降低内存峰值并更早进入索引阶段
                while len(pending_points) >= vector_points_batch_size:
                    points_batch = pending_points[:vector_points_batch_size]
                    pending_points = pending_points[vector_points_batch_size:]
                    try:
                        await vector_store.upsert(points_batch)
                        upserted_vectors += len(points_batch)
                    except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as e:
                        logger.error(f"向量批量存储失败: {e}", exc_info=True)

                processed_chunks += len(batch)
                now = monotonic()
                should_commit_progress = (
                    processed_chunks == total_chunks
                    or processed_chunks % progress_commit_every_chunks == 0
                    or (now - last_progress_commit_at) >= progress_commit_every_seconds
                )
                if should_commit_progress and total_chunks > 0:
                    document.chunk_count = processed_chunks
                    progress = 20 + int((processed_chunks / total_chunks) * 70)  # 20~90
                    await update_processing_meta(
                        phase="embedding",
                        progress=progress,
                        done_chunks=processed_chunks,
                        total_chunks=total_chunks,
                    )
                    last_progress_commit_at = now

            stage_done(
                "embedding",
                batches=embedded_batches,
                embedded_chunks=embedded_chunks,
                total_chunks=total_chunks,
            )

            # 统一批量写入文档分段
            if chunk_rows:
                await self.session.execute(insert(DocumentChunk), chunk_rows)
                await self.session.commit()
            stage_done("persist_chunks", persisted_chunks=len(chunk_rows))

            # 刷新剩余向量
            vector_store_success = True
            if pending_points:
                try:
                    await update_processing_meta(
                        phase="indexing",
                        progress=95,
                        done_chunks=total_chunks,
                        total_chunks=total_chunks,
                    )
                    success = await vector_store.upsert(pending_points)
                    if not success:
                        vector_store_success = False
                        logger.error(f"向量存储失败: upsert 返回 False")
                    else:
                        upserted_vectors += len(pending_points)
                        logger.info(
                            f"向量存储成功，共 {upserted_vectors} 个向量；文档分段入库 {len(chunk_rows)} 条"
                        )
                except (RuntimeError, ValueError, TypeError, OSError, AttributeError) as e:
                    vector_store_success = False
                    logger.error(f"向量存储失败: {e}", exc_info=True)
            stage_done("upsert_vectors", upserted_vectors=upserted_vectors)

            # 7. 更新文档状态和分段数
            document.chunk_count = len(chunks)
            
            # 检查向量存储是否成功
            if not vector_store_success:
                document.status = DocumentStatus.FAILED
                error_reason = "向量存储失败，文档分段已创建但向量未索引"
                document_meta = document.extra_metadata or {}
                processing_meta = (document_meta.get("processing") or {})
                processing_meta["error_reason"] = error_reason
                processing_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                document_meta["processing"] = processing_meta
                document.extra_metadata = document_meta
                await update_processing_meta(
                    phase="failed",
                    progress=0,
                    status=DocumentStatus.FAILED,
                )
                await self.document_repo.update(document)
                await self.session.commit()
                stage_done("finalize", chunk_count=document.chunk_count)
                logger.error(f"文档处理失败: {document.file_name}, 向量存储失败")
                return False
            else:
                document.status = DocumentStatus.COMPLETED
                await update_processing_meta(
                    phase="completed",
                    progress=100,
                    done_chunks=len(chunks),
                    total_chunks=len(chunks),
                    status=DocumentStatus.COMPLETED,
                )
                await self.document_repo.update(document)
                await self.session.commit()
                stage_done("finalize", chunk_count=document.chunk_count)
                logger.info(f"文档处理完成: {document.file_name}, 分段数: {document.chunk_count}")
                return True
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError, OSError, AttributeError) as e:
            logger.error(f"处理文档失败: {e}", exc_info=True)
            document.status = DocumentStatus.FAILED
            try:
                error_reason = str(e)[:300]
                await update_processing_meta(
                    phase="failed",
                    progress=0,
                    status=DocumentStatus.FAILED,
                )
                document_meta = document.extra_metadata or {}
                processing_meta = (document_meta.get("processing") or {})
                processing_meta["error_reason"] = error_reason
                processing_meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                document_meta["processing"] = processing_meta
                document.extra_metadata = document_meta
                await self.document_repo.update(document)
                await self.session.commit()
            except SQLAlchemyError as commit_err:
                logger.error(f"更新失败状态时提交失败: {commit_err}", exc_info=True)
                await self.session.rollback()
            return False

    async def get_document_segments(
        self,
        document_id: UUID,
        page: int = 1,
        page_size: int = 20
    ) -> Page:
        """获取文档分段列表"""
        # 将UUID转换为字符串格式
        document_id_str = str(document_id) if hasattr(document_id, 'hex') else document_id
        
        # 查询分段总数
        count_query = select(func.count()).select_from(DocumentChunk).where(
            DocumentChunk.document_id == document_id_str
        )
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        # 查询分段列表
        offset = (page - 1) * page_size
        query = select(DocumentChunk).where(
            DocumentChunk.document_id == document_id_str
        ).order_by(DocumentChunk.chunk_index).offset(offset).limit(page_size)
        
        result = await self.session.execute(query)
        chunks = result.scalars().all()

        # 转换为字典格式
        items = []
        for chunk in chunks:
            items.append({
                "id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "metadata": chunk.extra_metadata,
                "created_at": chunk.created_at.isoformat() if chunk.created_at else None
            })

        return Page(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )

    async def _concatenate_chunks_text(self, document_id_str: str) -> str:
        """按 chunk_index 拼接已入库分段，作为原文展示的兜底。"""
        query = (
            select(DocumentChunk.content)
            .where(DocumentChunk.document_id == document_id_str)
            .order_by(DocumentChunk.chunk_index)
        )
        result = await self.session.execute(query)
        parts = list(result.scalars().all())
        if not parts:
            return ""
        return "\n\n".join(parts)

    async def get_document_original_text(self, document_id: UUID) -> str:
        """获取文档展示用全文：优先从源文件解析；失败或为空时用已索引分段拼接。"""
        document_id_str = str(document_id) if hasattr(document_id, "hex") else document_id
        document = await self.document_repo.get_by_id(document_id_str)
        if not document:
            raise ValueError("文档不存在")

        text = ""
        if document.file_path:
            source_path = self._resolve_source_path(document.file_path)
            if source_path.exists():
                from core.rag.document_processor import DocumentProcessor
                processor = DocumentProcessor()
                text = await processor.extract_text(
                    str(source_path),
                    document.file_type.value if hasattr(document.file_type, "value") else document.file_type
                ) or ""
            else:
                logger.warning(f"获取原文失败，源文件不存在: {source_path}")

        if text.strip():
            return text

        fallback = await self._concatenate_chunks_text(document_id_str)
        if fallback.strip():
            logger.info(
                "原文从源文件解析为空或文件缺失，已使用分段内容拼接, document_id=%s",
                document_id_str,
            )
        return fallback

    def _normalize_file_type(self, file_type: str) -> DocumentType:
        """标准化文件类型"""
        file_type_lower = file_type.lower()
        if file_type_lower in ["pdf", ".pdf"]:
            return DocumentType.PDF
        elif file_type_lower in ["docx", ".docx", "word"]:
            return DocumentType.DOCX
        elif file_type_lower in ["txt", ".txt", "text"]:
            return DocumentType.TXT
        elif file_type_lower in ["md", ".md", "markdown"]:
            return DocumentType.MD
        elif file_type_lower in ["html", ".html", "htm"]:
            return DocumentType.HTML
        elif file_type_lower in ["epub", ".epub"]:
            return DocumentType.EPUB
        elif file_type_lower in ["xlsx", ".xlsx"]:
            return DocumentType.XLSX
        elif file_type_lower in ["xls", ".xls"]:
            return DocumentType.XLS
        elif file_type_lower in ["csv", ".csv"]:
            return DocumentType.CSV
        elif file_type_lower in ["image", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]:
            return DocumentType.IMAGE
        else:
            return DocumentType.TXT

    def _normalize_knowledge_type(self, kt: str):
        """标准化知识分层类型"""
        from infrastructure.database.models import KnowledgeType
        kt_lower = kt.lower().strip()
        mapping = {
            "topic": KnowledgeType.TOPIC,
            "concept": KnowledgeType.CONCEPT,
            "summary": KnowledgeType.SUMMARY,
            "recipe": KnowledgeType.RECIPE,
            "reference": KnowledgeType.REFERENCE,
            "errata": KnowledgeType.ERRATA,
        }
        return mapping.get(kt_lower, None)
