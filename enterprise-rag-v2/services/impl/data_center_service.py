"""AI 工作台数据中心聚合查询。

该服务只负责跨领域只读统计和权限校验，业务状态变更仍由各领域 Service 负责。
"""

from typing import Any
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import (
    AgentRun,
    Asset,
    ContentDraft,
    ContentMetric,
    ContentPublishRecord,
    KnowledgeEvidence,
    KnowledgeItem,
    ResearchReport,
    ResearchRun,
)
from services.impl.asset_service import AssetServiceImpl


class DataCenterService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.access = AssetServiceImpl(session)

    async def overview(
        self,
        *,
        workspace_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool = False,
    ) -> dict[str, Any]:
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        workspace = str(workspace_id)
        tenant = str(tenant_id)

        assets = await self._status_section(Asset, workspace, tenant, include_deleted=False)
        knowledge = await self._status_section(KnowledgeItem, workspace, tenant)
        research = await self._status_section(ResearchRun, workspace, tenant)
        agents = await self._status_section(AgentRun, workspace, tenant)
        content_drafts = await self._status_section(ContentDraft, workspace, tenant)
        performance = await self._content_performance(workspace, tenant)
        health = await self._health(workspace, tenant, assets, knowledge, research, agents)
        return {
            "workspace_id": workspace,
            "assets": assets,
            "knowledge": knowledge,
            "research": research,
            "agents": agents,
            "content_drafts": content_drafts,
            "content_performance": performance,
            "health": health,
        }

    async def _status_section(
        self,
        model: Any,
        workspace_id: str,
        tenant_id: str,
        *,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        status_column = model.status if hasattr(model, "status") else model.review_status
        conditions = [model.workspace_id == workspace_id, model.tenant_id == tenant_id]
        if not include_deleted and hasattr(model, "deleted_at"):
            conditions.append(model.deleted_at.is_(None))
        result = await self.session.execute(
            select(status_column, func.count()).where(*conditions).group_by(status_column)
        )
        by_status = {str(status): int(count) for status, count in result.all()}
        return {"total": sum(by_status.values()), "by_status": by_status}

    async def _content_performance(self, workspace_id: str, tenant_id: str) -> dict[str, Any]:
        publish_conditions = [
            ContentPublishRecord.workspace_id == workspace_id,
            ContentPublishRecord.tenant_id == tenant_id,
        ]
        publish_count = int(
            await self.session.scalar(select(func.count()).select_from(ContentPublishRecord).where(*publish_conditions)) or 0
        )
        result = await self.session.execute(
            select(
                func.coalesce(func.sum(ContentMetric.impressions), 0),
                func.coalesce(func.sum(ContentMetric.clicks), 0),
                func.coalesce(func.sum(ContentMetric.likes), 0),
                func.coalesce(func.sum(ContentMetric.comments), 0),
                func.coalesce(func.sum(ContentMetric.shares), 0),
            ).where(ContentMetric.workspace_id == workspace_id, ContentMetric.tenant_id == tenant_id)
        )
        impressions, clicks, likes, comments, shares = (int(value or 0) for value in result.one())
        return {
            "publish_count": publish_count,
            "impressions": impressions,
            "clicks": clicks,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "click_through_rate": round(clicks / impressions, 4) if impressions else 0.0,
        }

    async def _health(
        self,
        workspace_id: str,
        tenant_id: str,
        assets: dict[str, Any],
        knowledge: dict[str, Any],
        research: dict[str, Any],
        agents: dict[str, Any],
    ) -> dict[str, Any]:
        approved_knowledge = int(
            await self.session.scalar(
                select(func.count()).select_from(KnowledgeItem).where(
                    KnowledgeItem.workspace_id == workspace_id,
                    KnowledgeItem.tenant_id == tenant_id,
                    KnowledgeItem.deleted_at.is_(None),
                    KnowledgeItem.review_status == "approved",
                )
            )
            or 0
        )
        evidenced_knowledge = int(
            await self.session.scalar(
                select(func.count(distinct(KnowledgeEvidence.knowledge_item_id)))
                .join(KnowledgeItem, KnowledgeItem.id == KnowledgeEvidence.knowledge_item_id)
                .where(
                    KnowledgeItem.workspace_id == workspace_id,
                    KnowledgeItem.tenant_id == tenant_id,
                    KnowledgeItem.deleted_at.is_(None),
                    KnowledgeItem.review_status == "approved",
                )
            )
            or 0
        )
        completed_reports = int(
            await self.session.scalar(
                select(func.count()).select_from(ResearchReport).where(
                    ResearchReport.workspace_id == workspace_id,
                    ResearchReport.tenant_id == tenant_id,
                )
            )
            or 0
        )
        return {
            "asset_processing_rate": _rate(assets["by_status"].get("completed", 0), assets["total"]),
            "knowledge_evidence_coverage": _rate(evidenced_knowledge, approved_knowledge),
            "research_success_rate": _rate(research["by_status"].get("completed", 0), research["total"]),
            "agent_success_rate": _rate(agents["by_status"].get("completed", 0), agents["total"]),
            "approved_knowledge_count": approved_knowledge,
            "evidenced_knowledge_count": evidenced_knowledge,
            "research_report_count": completed_reports,
        }


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
