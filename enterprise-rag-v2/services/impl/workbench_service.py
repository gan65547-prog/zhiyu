"""工作台跨领域聚合查询，保持各业务模型的租户和工作空间边界。"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import AgentApproval, AgentDefinition, AgentRun, Asset, ContentDraft, ContentPublishRecord, ContentTopic, Dataset, Document, KnowledgeItem, ResearchProject, ResearchRun
from services.impl.asset_service import AssetServiceImpl


class WorkbenchService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.access = AssetServiceImpl(session)

    async def search(
        self,
        *,
        query: str,
        workspace_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        normalized = query.strip()
        if not normalized:
            return {"items": [], "total": 0, "query": normalized}
        pattern = f"%{normalized}%"
        items: list[dict[str, Any]] = []

        asset_result = await self.session.execute(
            select(Asset).where(
                Asset.tenant_id == str(tenant_id), Asset.workspace_id == str(workspace_id), Asset.deleted_at.is_(None),
                or_(Asset.title.ilike(pattern), Asset.source_uri.ilike(pattern)),
            ).order_by(Asset.created_at.desc()).limit(limit)
        )
        items.extend(self._item(asset.id, "asset", asset.title, asset.source_uri or "", "/assets", asset.created_at) for asset in asset_result.scalars())

        dataset_result = await self.session.execute(
            select(Dataset).where(
                Dataset.workspace_id == str(workspace_id),
                or_(Dataset.name.ilike(pattern), Dataset.description.ilike(pattern)),
            ).order_by(Dataset.created_at.desc()).limit(limit)
        )
        items.extend(
            self._item(dataset.id, "dataset", dataset.name, dataset.description or "", f"/datasets/{dataset.id}", dataset.created_at)
            for dataset in dataset_result.scalars()
        )

        document_result = await self.session.execute(
            select(Document, Dataset)
            .join(Dataset, Document.dataset_id == Dataset.id)
            .where(
                Dataset.workspace_id == str(workspace_id),
                Document.file_name.ilike(pattern),
            )
            .order_by(Document.created_at.desc()).limit(limit)
        )
        items.extend(
            self._item(
                document.id,
                "document",
                document.file_name,
                f"知识库：{dataset.name}",
                f"/documents/{document.id}/read",
                document.created_at,
                {"dataset_id": str(dataset.id), "status": str(document.status)},
            )
            for document, dataset in document_result.all()
        )

        knowledge_result = await self.session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.tenant_id == str(tenant_id), KnowledgeItem.workspace_id == str(workspace_id), KnowledgeItem.deleted_at.is_(None),
                or_(KnowledgeItem.title.ilike(pattern), KnowledgeItem.definition.ilike(pattern), KnowledgeItem.details.ilike(pattern)),
            ).order_by(KnowledgeItem.created_at.desc()).limit(limit)
        )
        items.extend(self._item(item.id, "knowledge", item.title, item.definition, "/knowledge", item.created_at, {"review_status": item.review_status}) for item in knowledge_result.scalars())

        project_result = await self.session.execute(
            select(ResearchProject).where(
                ResearchProject.tenant_id == str(tenant_id), ResearchProject.workspace_id == str(workspace_id), ResearchProject.deleted_at.is_(None),
                or_(ResearchProject.name.ilike(pattern), ResearchProject.description.ilike(pattern)),
            ).order_by(ResearchProject.created_at.desc()).limit(limit)
        )
        items.extend(self._item(project.id, "research", project.name, project.description or "", "/research", project.created_at, {"status": project.status}) for project in project_result.scalars())

        topic_result = await self.session.execute(
            select(ContentTopic).where(
                ContentTopic.tenant_id == str(tenant_id), ContentTopic.workspace_id == str(workspace_id),
                or_(ContentTopic.title.ilike(pattern), ContentTopic.brief.ilike(pattern)),
            ).order_by(ContentTopic.created_at.desc()).limit(limit)
        )
        items.extend(self._item(topic.id, "content_topic", topic.title, topic.brief or "", "/content", topic.created_at) for topic in topic_result.scalars())

        draft_result = await self.session.execute(
            select(ContentDraft).where(
                ContentDraft.tenant_id == str(tenant_id), ContentDraft.workspace_id == str(workspace_id),
                or_(ContentDraft.title.ilike(pattern), ContentDraft.body.ilike(pattern)),
            ).order_by(ContentDraft.created_at.desc()).limit(limit)
        )
        items.extend(self._item(draft.id, "content_draft", draft.title, draft.body, "/content", draft.created_at, {"review_status": draft.review_status}) for draft in draft_result.scalars())

        items.sort(key=lambda item: _datetime_sort_value(item.get("created_at")), reverse=True)
        return {"items": items[:limit], "total": len(items), "query": normalized}

    async def list_tasks(
        self,
        *,
        workspace_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool = False,
        limit: int = 100,
        include_history: bool = False,
    ) -> dict[str, Any]:
        """聚合需要用户处理或关注的任务，不改变各领域状态机。"""

        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        tasks: list[dict[str, Any]] = []
        tasks.extend(await self._asset_tasks(workspace_id, tenant_id, limit))
        tasks.extend(await self._knowledge_tasks(workspace_id, tenant_id, limit))
        tasks.extend(await self._approval_tasks(workspace_id, tenant_id, limit))
        tasks.extend(await self._content_tasks(workspace_id, tenant_id, limit))
        tasks.extend(await self._runtime_tasks(workspace_id, tenant_id, limit, include_history=include_history))
        tasks.sort(
            key=lambda item: (item["priority"], _datetime_sort_value(item.get("created_at"))),
            reverse=True,
        )
        return {"items": tasks[:limit], "total": len(tasks)}

    async def _asset_tasks(self, workspace_id: UUID, tenant_id: UUID, limit: int) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(Asset).where(
                Asset.tenant_id == str(tenant_id), Asset.workspace_id == str(workspace_id),
                Asset.deleted_at.is_(None), Asset.status.in_(["pending", "processing", "failed"]),
            ).order_by(Asset.updated_at.desc()).limit(limit)
        )
        return [self._task(item.id, "asset", item.title, _asset_task_status(item.status), f"/assets?asset_id={item.id}", item.updated_at, item.status == "failed") for item in result.scalars()]

    async def _knowledge_tasks(self, workspace_id: UUID, tenant_id: UUID, limit: int) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.tenant_id == str(tenant_id), KnowledgeItem.workspace_id == str(workspace_id),
                KnowledgeItem.deleted_at.is_(None), KnowledgeItem.review_status == "draft",
            ).order_by(KnowledgeItem.updated_at.desc()).limit(limit)
        )
        return [self._task(item.id, "knowledge_review", item.title, "待审核", f"/knowledge?item_id={item.id}", item.updated_at, True) for item in result.scalars()]

    async def _approval_tasks(self, workspace_id: UUID, tenant_id: UUID, limit: int) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(AgentApproval).where(
                AgentApproval.tenant_id == str(tenant_id), AgentApproval.workspace_id == str(workspace_id),
                AgentApproval.status == "pending",
            ).order_by(AgentApproval.created_at.desc()).limit(limit)
        )
        return [self._task(item.id, "agent_approval", f"Agent 审批 · {item.id}", "待审批", f"/agents?run_id={item.agent_run_id}", item.created_at, True, {"agent_run_id": item.agent_run_id}) for item in result.scalars()]

    async def _content_tasks(self, workspace_id: UUID, tenant_id: UUID, limit: int) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        result = await self.session.execute(
            select(ContentDraft).where(
                ContentDraft.tenant_id == str(tenant_id), ContentDraft.workspace_id == str(workspace_id),
                ContentDraft.review_status == "pending",
            ).order_by(ContentDraft.updated_at.desc()).limit(limit)
        )
        tasks.extend(self._task(item.id, "content_review", item.title, "草稿待审", f"/content?draft_id={item.id}", item.updated_at, True) for item in result.scalars())
        publish_result = await self.session.execute(
            select(ContentPublishRecord).where(
                ContentPublishRecord.tenant_id == str(tenant_id), ContentPublishRecord.workspace_id == str(workspace_id),
                ContentPublishRecord.status.in_(["ready", "failed"]),
            ).order_by(ContentPublishRecord.created_at.desc()).limit(limit)
        )
        tasks.extend(
            self._task(
                item.id, "content_publish", f"内容发布 · {item.platform}",
                "待人工确认" if item.status == "ready" else "发布失败待处理", f"/content?publish_id={item.id}", item.created_at, True,
                {"publish_status": item.status, "draft_id": item.draft_id},
            )
            for item in publish_result.scalars()
        )
        return tasks

    async def _runtime_tasks(self, workspace_id: UUID, tenant_id: UUID, limit: int, *, include_history: bool = False) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        active_statuses = {"pending", "queued", "running", "processing", "waiting_review", "failed", "error", "rejected"}
        agent_conditions = [AgentRun.tenant_id == str(tenant_id), AgentRun.workspace_id == str(workspace_id), AgentRun.research_run_id.is_(None)]
        research_conditions = [ResearchRun.tenant_id == str(tenant_id), ResearchRun.workspace_id == str(workspace_id)]
        if not include_history:
            agent_conditions.append(AgentRun.status.in_(active_statuses))
            research_conditions.append(ResearchRun.status.in_(active_statuses))
        agent_result = await self.session.execute(
            select(AgentRun, AgentDefinition)
            .join(AgentDefinition, AgentRun.definition_id == AgentDefinition.id)
            .where(*agent_conditions)
            .order_by(AgentRun.updated_at.desc()).limit(limit)
        )
        tasks.extend(
            self._task(
                run.id, "agent_run", f"Agent 运行 · {definition.name}", _runtime_task_status(run.status), f"/agents?run_id={run.id}", run.updated_at,
                run.status in {"failed", "waiting_review"},
                {"description": run.error_message or (f"当前步骤：{run.current_step}" if run.current_step else "已进入 Agent 审计时间线"), "current_step": run.current_step, "error_message": run.error_message, "agent_run_id": str(run.id)},
            )
            for run, definition in agent_result.all()
        )

        research_result = await self.session.execute(
            select(ResearchRun, ResearchProject)
            .join(ResearchProject, ResearchRun.project_id == ResearchProject.id)
            .where(*research_conditions)
            .order_by(ResearchRun.updated_at.desc()).limit(limit)
        )
        tasks.extend(
            self._task(
                run.id, "research_run", f"研究运行 · {project.name}", _runtime_task_status(run.status), f"/research?run_id={run.id}", run.updated_at,
                run.status in {"failed", "waiting_review"},
                {"description": run.error_message or (f"当前阶段：{run.current_stage}" if run.current_stage else "已进入研究审计时间线"), "current_stage": run.current_stage, "error_message": run.error_message, "research_run_id": str(run.id)},
            )
            for run, project in research_result.all()
        )
        return tasks
        return tasks

    @staticmethod
    def _task(resource_id: Any, kind: str, title: str, task_status: str, route: str, created_at: Any, urgent: bool, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"id": resource_id, "kind": kind, "title": title, "status": task_status, "priority": 2 if urgent else 1, "route": route, "created_at": created_at, "metadata": metadata or {}}

    @staticmethod
    def _item(resource_id: Any, kind: str, title: str, snippet: str, route: str, created_at: Any, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"id": resource_id, "kind": kind, "title": title, "snippet": snippet[:240], "route": route, "created_at": created_at, "metadata": metadata or {}}


def _asset_task_status(status: str) -> str:
    return {"pending": "待处理", "processing": "处理中", "failed": "失败待处理"}.get(status, status)


def _runtime_task_status(status: str) -> str:
    return {
        "pending": "pending", "queued": "queued", "running": "running", "processing": "processing",
        "waiting_review": "waiting_approval", "completed": "completed", "failed": "failed",
        "cancelled": "cancelled", "canceled": "cancelled", "rejected": "failed",
    }.get(status, status)


def _datetime_sort_value(value: Any) -> float:
    """Convert database datetimes to a comparable UTC timestamp."""
    if not isinstance(value, datetime):
        return float("-inf")
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return normalized.timestamp()
