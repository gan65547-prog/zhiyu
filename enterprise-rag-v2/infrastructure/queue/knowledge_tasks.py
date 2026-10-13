"""素材整理与知识提炼 Agent：只生成待审核知识草稿，不直接发布正式知识。"""

import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from infrastructure.database.models import Asset, Document, DocumentChunk, KnowledgeEvidence, KnowledgeItem, AgentRun
from infrastructure.database.session import AsyncSessionLocal
from infrastructure.logging.logger import get_logger
from infrastructure.queue.celery_app import celery_app
from infrastructure.queue.celery_asyncio import run_coroutine
from services.impl.agent_runtime_service import AgentRuntimeService

logger = get_logger("infrastructure.queue.knowledge_tasks")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _tags(text: str) -> list[str]:
    words = re.findall(r"[\u4e00-\u9fff]{2,8}|[A-Za-z][A-Za-z0-9_-]{2,20}", text)
    return list(dict.fromkeys(words))[:8]


async def _organize_asset_async(asset_id: str, tenant_id: str, user_id: str) -> dict:
    async with AsyncSessionLocal() as session:
        asset = await session.scalar(select(Asset).where(Asset.id == asset_id, Asset.tenant_id == tenant_id, Asset.deleted_at.is_(None)))
        if asset is None:
            raise LookupError("素材不存在")
        agent_run = await session.scalar(select(AgentRun).where(AgentRun.id == asset.extra_metadata.get("organize_agent_run_id", "") if isinstance(asset.extra_metadata, dict) else ""))
        if agent_run is None:
            raise LookupError("素材整理 Agent 运行不存在")
        runtime = AgentRuntimeService(session)
        try:
            agent_run.status, agent_run.current_step, agent_run.progress, agent_run.started_at = "running", "read_material", 10, _utcnow()
            await runtime.mark_step(agent_run_id=agent_run.id, step_key="read_material", status="running")
            document = await session.get(Document, str(asset.legacy_document_id)) if asset.legacy_document_id else None
            chunks = list((await session.execute(select(DocumentChunk).where(DocumentChunk.document_id == str(document.id)).order_by(DocumentChunk.chunk_index.asc()).limit(5))).scalars().all()) if document else []
            if not chunks:
                raise ValueError("素材尚未完成解析，无法提炼知识")
            text = "\n".join(chunk.content for chunk in chunks)
            summary = text[:1200].strip()
            tags = _tags(text)
            await runtime.mark_step(agent_run_id=agent_run.id, step_key="read_material", status="completed", output={"chunk_count": len(chunks)})
            await runtime.mark_step(agent_run_id=agent_run.id, step_key="summarize", status="completed", output={"summary_chars": len(summary)})
            await runtime.mark_step(agent_run_id=agent_run.id, step_key="extract_tags", status="completed", output={"tags": tags})
            item = KnowledgeItem(tenant_id=asset.tenant_id, workspace_id=asset.workspace_id, created_by=asset.created_by, title=asset.title, item_type="summary", definition=summary, details="由素材整理 Agent 生成，需人工审核后进入正式知识库。", conclusions=[summary], confidence=0.4, review_status="draft", extra_metadata={"auto_generated": True, "agent_run_id": str(agent_run.id), "tags": tags}, created_at=_utcnow(), updated_at=_utcnow())
            session.add(item)
            await session.flush()
            for chunk in chunks[:3]:
                session.add(KnowledgeEvidence(tenant_id=asset.tenant_id, workspace_id=asset.workspace_id, knowledge_item_id=item.id, asset_id=asset.id, document_id=document.id, chunk_id=chunk.id, quote=chunk.content[:1200], locator=f"chunk:{chunk.chunk_index}", source_uri=asset.source_uri, created_by=asset.created_by, created_at=_utcnow()))
            await runtime.mark_step(agent_run_id=agent_run.id, step_key="propose_knowledge", status="completed", output={"knowledge_item_id": str(item.id), "evidence_count": min(3, len(chunks))})
            await runtime.request_approval(agent_run_id=agent_run.id, step_key="human_review")
            agent_run.status, agent_run.current_step, agent_run.progress = "waiting_approval", "human_review", 90
            await session.commit()
            return {"asset_id": asset_id, "agent_run_id": str(agent_run.id), "knowledge_item_id": str(item.id), "status": "waiting_approval"}
        except Exception as exc:
            agent_run.status, agent_run.current_step, agent_run.error_message = "failed", "failed", str(exc)[:2000]
            await session.commit()
            logger.exception("素材知识提炼失败 asset_id=%s", asset_id)
            raise


@celery_app.task(name="knowledge.organize_asset", bind=True, max_retries=1, default_retry_delay=30)
def organize_asset_task(self, asset_id: str, tenant_id: str, user_id: str) -> dict:
    try:
        return run_coroutine(_organize_asset_async(asset_id, tenant_id, user_id))
    except (ConnectionError, TimeoutError) as exc:
        raise self.retry(exc=exc)
