"""知识卡片 → 基座 RAG 回流服务。

审核通过的知识卡片渲染为 Markdown 文档，挂到所属 workspace 的
「知识卡片」系统数据集，走既有文档索引管线进入 chat 检索链路。
卡片回到 draft 或回滚时同步移除检索痕迹。

顺序约束：更新/移除场景必须先删除旧向量再落新内容——宁可短暂检索
不到，不允许已被推翻的旧结论继续被命中。
"""

import json
import logging
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import Dataset, Document, DocumentChunk, KnowledgeItem

logger = logging.getLogger(__name__)

BACKFLOW_DATASET_NAME = "知识卡片"
CARD_FILE_PREFIX = "knowledge-card-"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def backflow_enabled() -> bool:
    return os.getenv("KNOWLEDGE_BACKFLOW_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def card_file_name(item_id: UUID | str) -> str:
    return f"{CARD_FILE_PREFIX}{item_id}.md"


def _evidence_lines(evidence) -> list[str]:
    rows = [row for row in (evidence or []) if getattr(row, "quote", None)]
    if not rows:
        return []
    lines = ["## 证据", ""]
    for row in rows:
        locator = f"（{row.locator}）" if getattr(row, "locator", None) else ""
        lines.append(f"> {row.quote}{locator}")
    lines.append("")
    return lines


def _metadata_lines(metadata: dict) -> list[str]:
    if not metadata:
        return []
    return ["## 元数据", "", "```json", json.dumps(metadata, ensure_ascii=False, default=str, indent=2), "```", ""]


def render_card_markdown(item: KnowledgeItem, evidence=None) -> str:
    lines = [f"# {item.title or '知识卡片'}", ""]
    lines.append(f"- 类型：{item.item_type or 'concept'}")
    lines.append(f"- 置信度：{item.confidence}")
    lines.append(f"- 卡片ID：{item.id}")
    lines.append("")
    if item.definition:
        lines += ["## 定义", "", str(item.definition), ""]
    if item.details:
        lines += ["## 详情", "", str(item.details), ""]
    conclusions = list(item.conclusions or [])
    if conclusions:
        lines += ["## 结论", ""]
        lines += [f"- {conclusion}" for conclusion in conclusions]
        lines.append("")
    lines += _evidence_lines(evidence)
    lines += _metadata_lines(dict(item.extra_metadata or {}))
    return "\n".join(lines)


class KnowledgeBackflowService:
    def __init__(self, session: AsyncSession, document_service=None, indexing_service=None):
        self.session = session
        self._document_service = document_service
        self._indexing_service = indexing_service

    @property
    def document_service(self):
        if self._document_service is None:
            from services.impl.document_service import DocumentServiceImpl
            self._document_service = DocumentServiceImpl(self.session)
        return self._document_service

    @property
    def indexing_service(self):
        if self._indexing_service is None:
            from services.impl.document_indexing_service import DocumentIndexingService
            self._indexing_service = DocumentIndexingService(self.session)
        return self._indexing_service

    async def sync_to_rag(self, item: KnowledgeItem, evidence=None) -> dict | None:
        """approve 钩子：幂等同步卡片为基座文档并触发索引。

        先提交审批事务保证 worker 可见，文档阶段失败只影响回流，
        审批状态不受影响（失败记日志，可通过再次审核重触发）。
        """
        if not backflow_enabled():
            return None
        await self.session.commit()
        try:
            result = await self._sync(item, evidence)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            logger.exception("知识卡片回流失败 item_id=%s", item.id)
            return None
        await self._dispatch_indexing(result["document_id"])
        return result

    async def remove_from_rag(self, item: KnowledgeItem) -> None:
        """回 draft / 回滚钩子：删除已回流文档与其向量，幂等。"""
        if not backflow_enabled():
            return
        document = await self._find_document(item)
        if document is None:
            return
        await self.indexing_service.delete_document_vectors(UUID(str(document.id)), workspace_id=str(item.workspace_id))
        # Document→chunks 的 ORM 级联在 async 下需要懒加载，改用批量删除
        await self.session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == str(document.id)))
        await self.session.execute(delete(Document).where(Document.id == str(document.id)))
        await self.session.commit()

    async def _sync(self, item: KnowledgeItem, evidence) -> dict:
        dataset = await self._resolve_backflow_dataset(UUID(str(item.workspace_id)))
        markdown = render_card_markdown(item, evidence)
        document = await self._find_document(item, dataset_id=dataset.id)
        if document is None:
            file_path = self._card_file_path(item.id)
            Path(file_path).write_text(markdown, encoding="utf-8")
            created = await self.document_service.upload_document(
                dataset_id=UUID(str(dataset.id)),
                file_path=file_path,
                file_name=card_file_name(item.id),
                file_type=".md",
                file_size=Path(file_path).stat().st_size,
            )
            # upload_document 的 metadata kwarg 落在未映射的保留属性上，不会持久化
            row = await self.session.get(Document, str(created["id"]))
            row.extra_metadata = self._document_metadata(item)
            await self.session.flush()
            return {"document_id": str(created["id"]), "action": "created"}
        Path(self._card_file_path(item.id)).write_text(markdown, encoding="utf-8")
        document.extra_metadata = self._document_metadata(item)
        document.file_size = len(markdown.encode("utf-8"))
        await self.document_service.reindex_document(UUID(str(document.id)), force=True)
        return {"document_id": str(document.id), "action": "updated"}

    async def _resolve_backflow_dataset(self, workspace_id: UUID) -> Dataset:
        result = await self.session.execute(
            select(Dataset).where(Dataset.workspace_id == str(workspace_id), Dataset.name == BACKFLOW_DATASET_NAME)
        )
        dataset = result.scalar_one_or_none()
        if dataset is not None:
            return dataset
        dataset = Dataset(
            workspace_id=str(workspace_id),
            name=BACKFLOW_DATASET_NAME,
            description="知识卡片审核通过后的自动回流数据集",
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            extra_metadata={"is_system": True, "purpose": "knowledge_backflow"},
        )
        self.session.add(dataset)
        await self.session.flush()
        return dataset

    async def _find_document(self, item: KnowledgeItem, dataset_id=None):
        query = select(Document).where(
            Document.file_name == card_file_name(item.id),
        )
        if dataset_id is not None:
            query = query.where(Document.dataset_id == str(dataset_id))
        else:
            result = await self.session.execute(
                select(Dataset.id).where(
                    Dataset.workspace_id == str(item.workspace_id), Dataset.name == BACKFLOW_DATASET_NAME
                )
            )
            dataset_ids = [str(row) for row in result.scalars().all()]
            if not dataset_ids:
                return None
            query = query.where(Document.dataset_id.in_(dataset_ids))
        return (await self.session.execute(query)).scalar_one_or_none()

    def _card_file_path(self, item_id: UUID | str) -> str:
        upload_dir = Path("./uploads")
        upload_dir.mkdir(exist_ok=True)
        return str(upload_dir / card_file_name(item_id))

    def _document_metadata(self, item: KnowledgeItem) -> dict:
        return {
            "source": "knowledge_card",
            "knowledge_item_id": str(item.id),
            "workspace_id": str(item.workspace_id),
            "review_status": item.review_status,
            "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        }

    async def _dispatch_indexing(self, document_id: str) -> None:
        try:
            from infrastructure.queue.document_tasks import process_document_task
            process_document_task.apply_async(args=[str(document_id)], queue="documents_high")
        except Exception as exc:
            logger.warning("知识卡片索引任务提交失败 document_id=%s error=%s", document_id, exc)
