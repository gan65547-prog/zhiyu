"""研究结果到内容草稿的受控编排服务。"""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import ContentDraft, ResearchReport, ResearchRun
from services.impl.content_service import ContentService
from services.impl.research_service import ResearchService


class ContentGenerationService:
    """只允许审核通过的研究报告进入内容审核队列。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.research = ResearchService(session)
        self.content = ContentService(session)

    async def create_draft_from_report(
        self,
        *,
        report_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool,
        title: Optional[str] = None,
        topic_id: Optional[UUID] = None,
    ) -> Optional[dict[str, Any]]:
        report = await self._approved_report(report_id, tenant_id, user_id, is_superuser)
        if report is None:
            return None
        run = await self.session.scalar(
            select(ResearchRun).where(
                ResearchRun.id == str(report["run_id"]),
                ResearchRun.tenant_id == str(tenant_id),
            )
        )
        if run is None:
            return None
        existing = await self._existing_draft(
            report_id=report_id,
            workspace_id=UUID(str(run.workspace_id)),
            tenant_id=tenant_id,
        )
        if existing is not None:
            return self.content._draft_dict(existing)
        evidence = await self.research.list_evidence(
            run_id=UUID(str(run.id)), tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser,
        )
        findings = await self.research.list_findings(
            run_id=UUID(str(run.id)), tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser,
        )
        if evidence is None or findings is None:
            return None
        generated_title = title.strip() if title and title.strip() else f"研究报告内容草稿-{str(report_id)[:8]}"
        body = f"{str(report['content_markdown']).strip()}\n\n---\n来源：审核通过的研究报告 `{report_id}`。"
        return await self.content.create_draft(
            tenant_id=tenant_id,
            user_id=user_id,
            is_superuser=is_superuser,
            data={
                "workspace_id": UUID(str(run.workspace_id)),
                "topic_id": topic_id,
                "title": generated_title,
                "body": body,
                "metadata": {
                    "source_type": "research_report",
                    "research_report_id": str(report_id),
                    "research_run_id": str(run.id),
                    "review_status": report["review_status"],
                    "citation_completeness": report["citation_completeness"],
                    "evidence_ids": [str(item["id"]) for item in evidence],
                    "finding_ids": [str(item["id"]) for item in findings],
                    "requires_human_review": True,
                },
            },
        )

    async def _existing_draft(
        self, *, report_id: UUID, workspace_id: UUID, tenant_id: UUID,
    ) -> Optional[ContentDraft]:
        result = await self.session.execute(
            select(ContentDraft).where(
                ContentDraft.tenant_id == str(tenant_id),
                ContentDraft.workspace_id == str(workspace_id),
            ).order_by(ContentDraft.created_at.asc())
        )
        for draft in result.scalars().all():
            if str((draft.metadata_json or {}).get("research_report_id")) == str(report_id):
                return draft
        return None

    async def _approved_report(
        self, report_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool,
    ) -> Optional[dict[str, Any]]:
        report = await self.session.scalar(
            select(ResearchReport).where(
                ResearchReport.id == str(report_id), ResearchReport.tenant_id == str(tenant_id),
            )
        )
        if report is None:
            return None
        accessible = await self.research.get_report(
            run_id=UUID(str(report.run_id)), tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser,
        )
        if accessible is None:
            return None
        if accessible["review_status"] != "approved":
            raise ValueError("只有审核通过的研究报告才能生成内容草稿")
        if not str(accessible["content_markdown"]).strip():
            raise ValueError("研究报告内容为空，不能生成内容草稿")
        return accessible
