"""研究项目和运行生命周期服务。"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import (
    Asset,
    Dataset,
    ResearchProject,
    ResearchQuestion,
    ResearchReport,
    ResearchEvidence,
    ResearchSource,
    ResearchFinding,
    ResearchRun,
    ResearchSample,
    Dataset,
    AgentRun,
    AgentApproval,
)
from services.impl.asset_service import AssetServiceImpl
from services.impl.asset_ingestion_service import AssetIngestionService
from services.impl.dataset_service import DatasetServiceImpl
from services.impl.agent_runtime_service import AgentRuntimeService
from services.impl.knowledge_service import KnowledgeService
from services.impl.safe_fetcher import SafeFetcher


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled"}


class ResearchService:
    """研究应用服务；只负责边界、状态和数据关系，执行交给 worker。"""

    def __init__(self, session: AsyncSession, quota_service=None):
        self.session = session
        self.quota_service = quota_service
        self.access = AssetServiceImpl(session)
        self.fetcher = SafeFetcher()

    async def _reserve_research_quota(self, tenant_id: UUID, limits: dict[str, Any]) -> list[tuple[str, int]]:
        if self.quota_service is None:
            return []
        reservations = [
            ("research_runs_monthly", 1),
            ("research_sources_monthly", int(limits["max_sources"])),
            ("research_output_tokens_monthly", int(limits["max_output_tokens"])),
        ]
        reserved: list[tuple[str, int]] = []
        try:
            for dimension, amount in reservations:
                await self.quota_service.check_and_increment(str(tenant_id), dimension, amount)
                reserved.append((dimension, amount))
        except Exception:
            for dimension, amount in reversed(reserved):
                await self.quota_service.decrement_usage(str(tenant_id), dimension, amount)
            raise
        return reserved

    async def _release_research_quota(self, tenant_id: UUID, reservations: list[tuple[str, int]]) -> None:
        if self.quota_service is None:
            return
        for dimension, amount in reversed(reservations):
            await self.quota_service.decrement_usage(str(tenant_id), dimension, amount)

    async def _verify_project_access(self, project: ResearchProject, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> None:
        await self.access._verify_workspace_access(UUID(str(project.workspace_id)), tenant_id, user_id, is_superuser)

    async def _get_project(self, project_id: UUID, tenant_id: UUID) -> Optional[ResearchProject]:
        result = await self.session.execute(
            select(ResearchProject).where(
                ResearchProject.id == str(project_id), ResearchProject.tenant_id == str(tenant_id), ResearchProject.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def _questions(self, project_id: UUID) -> list[ResearchQuestion]:
        result = await self.session.execute(
            select(ResearchQuestion).where(ResearchQuestion.project_id == str(project_id)).order_by(ResearchQuestion.sort_order.asc())
        )
        return list(result.scalars().all())

    async def _sample_count(self, project_id: UUID) -> int:
        return int(await self.session.scalar(select(func.count(ResearchSample.id)).where(ResearchSample.project_id == str(project_id))) or 0)

    async def _project_dict(self, project: ResearchProject) -> dict[str, Any]:
        return {
            "id": project.id, "tenant_id": project.tenant_id, "workspace_id": project.workspace_id,
            "created_by": project.created_by, "name": project.name, "description": project.description,
            "status": project.status,
            "questions": [{"question": q.question, "sort_order": q.sort_order} for q in await self._questions(project.id)],
            "sample_count": await self._sample_count(project.id),
            "created_at": project.created_at, "updated_at": project.updated_at,
        }

    async def _run_dict(self, run: ResearchRun) -> dict[str, Any]:
        report_id = await self.session.scalar(select(ResearchReport.id).where(ResearchReport.run_id == str(run.id)))
        agent_run_id = await self.session.scalar(select(AgentRun.id).where(AgentRun.research_run_id == str(run.id)))
        return {
            "id": run.id, "project_id": run.project_id, "status": run.status,
            "progress": run.progress, "current_stage": run.current_stage,
            "error_message": run.error_message, "report_id": report_id, "agent_run_id": agent_run_id,
            "created_at": run.created_at, "updated_at": run.updated_at,
        }

    async def _verify_samples(self, tenant_id: UUID, workspace_id: UUID, samples: list[dict[str, Any]]) -> None:
        for sample in samples:
            if not any((sample.get("asset_id"), sample.get("dataset_id"), sample.get("source_uri"))):
                raise ValueError("研究样本必须绑定 Asset、Dataset 或 URL")
            if sample.get("asset_id"):
                result = await self.session.execute(select(Asset.id).where(Asset.id == str(sample["asset_id"]), Asset.tenant_id == str(tenant_id), Asset.workspace_id == str(workspace_id), Asset.deleted_at.is_(None)))
                if result.scalar_one_or_none() is None:
                    raise PermissionError("研究样本素材不存在或无权访问")
            if sample.get("dataset_id"):
                result = await self.session.execute(select(Dataset.id).where(Dataset.id == str(sample["dataset_id"]), Dataset.workspace_id == str(workspace_id)))
                if result.scalar_one_or_none() is None:
                    raise PermissionError("研究样本知识库不存在或不属于当前工作空间")
            if sample.get("source_uri"):
                await self.fetcher._validate_url(str(sample["source_uri"]))

    async def create_project(self, *, tenant_id: UUID, user_id: UUID, is_superuser: bool, data: dict[str, Any]) -> dict[str, Any]:
        workspace_id = data.pop("workspace_id")
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        questions = data.pop("questions", [])
        samples = data.pop("samples", [])
        metadata = data.pop("metadata", {})
        await self._verify_samples(tenant_id, workspace_id, samples)
        project = ResearchProject(tenant_id=str(tenant_id), workspace_id=str(workspace_id), created_by=str(user_id), extra_metadata=metadata, **data)
        self.session.add(project)
        await self.session.flush()
        for question in questions:
            self.session.add(ResearchQuestion(tenant_id=str(tenant_id), workspace_id=str(workspace_id), project_id=str(project.id), **question))
        for sample in samples:
            self.session.add(ResearchSample(tenant_id=str(tenant_id), workspace_id=str(workspace_id), project_id=str(project.id), created_by=str(user_id), **sample))
        await self.session.flush()
        return await self._project_dict(project)

    async def list_projects(self, *, tenant_id: UUID, workspace_id: UUID, user_id: UUID, page: int, page_size: int, is_superuser: bool) -> dict[str, Any]:
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        conditions = [ResearchProject.tenant_id == str(tenant_id), ResearchProject.workspace_id == str(workspace_id), ResearchProject.deleted_at.is_(None)]
        total = int(await self.session.scalar(select(func.count(ResearchProject.id)).where(*conditions)) or 0)
        result = await self.session.execute(select(ResearchProject).where(*conditions).order_by(ResearchProject.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
        return {"items": [await self._project_dict(item) for item in result.scalars().all()], "total": total, "page": page, "page_size": page_size}

    async def create_run(self, *, project_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, limits: dict[str, Any]) -> dict[str, Any]:
        project = await self._get_project(project_id, tenant_id)
        if project is None:
            return None
        await self._verify_project_access(project, tenant_id, user_id, is_superuser)
        normalized_limits = dict(limits or {})
        for key, minimum, maximum in (("max_sources", 1, 1000), ("max_source_bytes", 1, 50 * 1024 * 1024), ("max_output_tokens", 256, 8000)):
            if key in normalized_limits:
                try:
                    normalized_limits[key] = int(normalized_limits[key])
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"{key} 必须是整数") from exc
                if not minimum <= normalized_limits[key] <= maximum:
                    raise ValueError(f"{key} 必须在 {minimum} 到 {maximum} 之间")
        # Keep the implicit browser/UI budget below the free monthly quota so a
        # tenant with a small amount of prior usage can still start a run.
        # Callers can explicitly request a larger budget when their plan allows it.
        normalized_limits.setdefault("max_sources", 10)
        normalized_limits.setdefault("max_source_bytes", 20 * 1024 * 1024)
        normalized_limits.setdefault("max_output_tokens", 3000)
        reservations = await self._reserve_research_quota(tenant_id, normalized_limits)
        try:
            run = ResearchRun(tenant_id=str(tenant_id), workspace_id=str(project.workspace_id), project_id=str(project.id), created_by=str(user_id), plan={"question_count": len(await self._questions(project.id)), "budget": normalized_limits}, limits=normalized_limits)
            self.session.add(run)
            await self.session.flush()
            await AgentRuntimeService(self.session).create_research_run(research_run=run, user_id=user_id)
        except Exception:
            await self._release_research_quota(tenant_id, reservations)
            raise
        return await self._run_dict(run)

    async def list_runs(self, *, project_id: UUID, tenant_id: UUID, user_id: UUID, page: int, page_size: int, is_superuser: bool) -> Optional[dict[str, Any]]:
        project = await self._get_project(project_id, tenant_id)
        if project is None:
            return None
        await self._verify_project_access(project, tenant_id, user_id, is_superuser)
        conditions = [ResearchRun.project_id == str(project.id), ResearchRun.tenant_id == str(tenant_id)]
        total = int(await self.session.scalar(select(func.count(ResearchRun.id)).where(*conditions)) or 0)
        result = await self.session.execute(select(ResearchRun).where(*conditions).order_by(ResearchRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
        return {"items": [await self._run_dict(item) for item in result.scalars().all()], "total": total, "page": page, "page_size": page_size}

    async def get_run(self, *, run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[dict[str, Any]]:
        result = await self.session.execute(select(ResearchRun).where(ResearchRun.id == str(run_id), ResearchRun.tenant_id == str(tenant_id)))
        run = result.scalar_one_or_none()
        if run is None:
            return None
        project = await self._get_project(UUID(str(run.project_id)), tenant_id)
        if project is None:
            return None
        await self._verify_project_access(project, tenant_id, user_id, is_superuser)
        return await self._run_dict(run)

    async def cancel_run(self, *, run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[dict[str, Any]]:
        result = await self.session.execute(select(ResearchRun).where(ResearchRun.id == str(run_id), ResearchRun.tenant_id == str(tenant_id)))
        run = result.scalar_one_or_none()
        if run is None:
            return None
        project = await self._get_project(UUID(str(run.project_id)), tenant_id)
        if project is None:
            return None
        await self._verify_project_access(project, tenant_id, user_id, is_superuser)
        if run.status not in TERMINAL_RUN_STATUSES:
            run.status = "cancelled"
            run.current_stage = "cancelled"
            agent_run = await self.session.scalar(select(AgentRun).where(AgentRun.research_run_id == str(run.id)))
            if agent_run and agent_run.status not in {"completed", "failed", "cancelled"}:
                agent_run.status = "cancelled"
                agent_run.current_step = "cancelled"
            await self.session.flush()
        return await self._run_dict(run)

    async def retry_run(self, *, run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[dict[str, Any]]:
        """重置失败/取消的研究运行，并由同一 Agent 运行继续投递。"""
        result = await self.session.execute(select(ResearchRun).where(
            ResearchRun.id == str(run_id), ResearchRun.tenant_id == str(tenant_id),
        ))
        run = result.scalar_one_or_none()
        if run is None:
            return None
        project = await self._get_project(UUID(str(run.project_id)), tenant_id)
        if project is None:
            return None
        await self._verify_project_access(project, tenant_id, user_id, is_superuser)
        if run.status not in {"failed", "cancelled"}:
            raise ValueError("只有失败或取消的研究运行可以重试")
        agent_run = await self.session.scalar(select(AgentRun).where(AgentRun.research_run_id == str(run.id)))
        if agent_run is None:
            raise ValueError("研究运行缺少 Agent 编排记录，无法重试")
        await AgentRuntimeService(self.session).retry_run(
            agent_run_id=UUID(str(agent_run.id)), tenant_id=tenant_id,
            user_id=user_id, is_superuser=is_superuser,
        )
        return await self._run_dict(run)

    async def get_report(self, *, run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[dict[str, Any]]:
        result = await self.session.execute(select(ResearchRun).where(ResearchRun.id == str(run_id), ResearchRun.tenant_id == str(tenant_id)))
        run = result.scalar_one_or_none()
        if run is None:
            return None
        project = await self._get_project(UUID(str(run.project_id)), tenant_id)
        if project is None:
            return None
        await self._verify_project_access(project, tenant_id, user_id, is_superuser)
        report_result = await self.session.execute(select(ResearchReport).where(ResearchReport.run_id == str(run.id)))
        report = report_result.scalar_one_or_none()
        if report is None:
            return None
        return {
            "id": report.id, "run_id": report.run_id, "version": report.version,
            "content_markdown": report.content_markdown, "content_json": report.content_json or {},
            "model_name": report.model_name, "prompt_version": report.prompt_version,
            "citation_completeness": report.citation_completeness, "review_status": report.review_status,
            "published_dataset_id": report.published_dataset_id, "published_document_id": report.published_document_id,
            "published_knowledge_item_id": report.published_knowledge_item_id,
            "created_at": report.created_at, "updated_at": report.updated_at,
        }

    async def update_report(self, *, report_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, content_markdown: str) -> Optional[dict[str, Any]]:
        report = await self.session.scalar(select(ResearchReport).where(
            ResearchReport.id == str(report_id), ResearchReport.tenant_id == str(tenant_id)
        ))
        if report is None:
            return None
        run = await self.session.get(ResearchRun, str(report.run_id))
        if run is None:
            return None
        project = await self._get_project(UUID(str(run.project_id)), tenant_id)
        if project is None:
            return None
        await self._verify_project_access(project, tenant_id, user_id, is_superuser)
        if report.published_dataset_id or report.published_document_id or report.published_knowledge_item_id:
            raise ValueError("已发布报告不能直接修改，请基于新的研究运行编辑")
        content = content_markdown.strip()
        if not content:
            raise ValueError("报告内容不能为空")
        report.content_markdown = content
        report.version += 1
        report.review_status = "draft"
        await self.session.flush()
        return await self.get_report(run_id=UUID(str(run.id)), tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser)

    async def _get_accessible_run(self, *, run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[ResearchRun]:
        run = await self.session.scalar(select(ResearchRun).where(ResearchRun.id == str(run_id), ResearchRun.tenant_id == str(tenant_id)))
        if run is None:
            return None
        project = await self._get_project(UUID(str(run.project_id)), tenant_id)
        if project is None:
            return None
        await self._verify_project_access(project, tenant_id, user_id, is_superuser)
        return run

    async def list_evidence(self, *, run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[list[dict[str, Any]]]:
        run = await self._get_accessible_run(run_id=run_id, tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser)
        if run is None:
            return None
        result = await self.session.execute(
            select(ResearchEvidence, ResearchSource).join(ResearchSource, ResearchSource.id == ResearchEvidence.source_id).where(
                ResearchEvidence.run_id == str(run.id), ResearchEvidence.tenant_id == str(tenant_id),
            ).order_by(ResearchEvidence.created_at.asc())
        )
        return [
            {"id": evidence.id, "run_id": evidence.run_id, "source_id": evidence.source_id, "quote": evidence.quote,
             "locator": evidence.locator, "source_title": source.title, "source_uri": source.source_uri, "created_at": evidence.created_at}
            for evidence, source in result.all()
        ]

    async def list_findings(self, *, run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[list[dict[str, Any]]]:
        run = await self._get_accessible_run(run_id=run_id, tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser)
        if run is None:
            return None
        result = await self.session.execute(
            select(ResearchFinding).where(
                ResearchFinding.run_id == str(run.id), ResearchFinding.tenant_id == str(tenant_id),
            ).order_by(ResearchFinding.created_at.asc())
        )
        return [
            {"id": finding.id, "run_id": finding.run_id, "claim": finding.claim, "claim_type": finding.claim_type,
             "confidence": finding.confidence, "evidence_ids": list(finding.evidence_ids or []),
             "needs_review": finding.needs_review, "review_status": finding.review_status, "created_at": finding.created_at}
            for finding in result.scalars().all()
        ]

    async def review_report(self, *, report_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, review_status: str) -> Optional[dict[str, Any]]:
        result = await self.session.execute(
            select(ResearchReport).where(ResearchReport.id == str(report_id), ResearchReport.tenant_id == str(tenant_id))
        )
        report = result.scalar_one_or_none()
        if report is None:
            return None
        run_result = await self.session.execute(select(ResearchRun).where(ResearchRun.id == str(report.run_id)))
        run = run_result.scalar_one_or_none()
        if run is None:
            return None
        project = await self._get_project(UUID(str(run.project_id)), tenant_id)
        if project is None:
            return None
        await self._verify_project_access(project, tenant_id, user_id, is_superuser)
        if review_status == "approved" and not report.content_markdown.strip():
            raise ValueError("空报告不能审核通过")
        report.review_status = review_status
        agent_run = await self.session.scalar(select(AgentRun).where(AgentRun.research_run_id == str(run.id)))
        if agent_run:
            approval = await self.session.scalar(
                select(AgentApproval).where(AgentApproval.agent_run_id == str(agent_run.id), AgentApproval.status == "pending").order_by(AgentApproval.created_at.desc())
            )
            if approval:
                approval.status = review_status
                approval.reviewer_id = str(user_id)
                approval.reviewed_at = _utcnow()
            agent_run.status = "completed" if review_status == "approved" else "rejected"
            agent_run.current_step = "human_review"
            agent_run.progress = 100 if review_status == "approved" else 90
        await self.session.flush()
        return await self.get_report(run_id=UUID(str(run.id)), tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser)

    async def publish_report(self, *, report_id: UUID, dataset_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[dict[str, Any]]:
        result = await self.session.execute(
            select(ResearchReport).where(ResearchReport.id == str(report_id), ResearchReport.tenant_id == str(tenant_id))
        )
        report = result.scalar_one_or_none()
        if report is None:
            return None
        run_result = await self.session.execute(select(ResearchRun).where(ResearchRun.id == str(report.run_id)))
        run = run_result.scalar_one_or_none()
        if run is None:
            return None
        project = await self._get_project(UUID(str(run.project_id)), tenant_id)
        if project is None:
            return None
        await self._verify_project_access(project, tenant_id, user_id, is_superuser)
        if report.review_status != "approved":
            raise ValueError("只有审核通过的报告才能发布")
        if report.published_dataset_id:
            if str(report.published_dataset_id) != str(dataset_id):
                raise ValueError("报告已经发布到其他数据集")
            return await self.get_report(run_id=UUID(str(run.id)), tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser)
        dataset_result = await self.session.execute(
            select(Dataset).where(Dataset.id == str(dataset_id), Dataset.workspace_id == str(project.workspace_id))
        )
        dataset = dataset_result.scalar_one_or_none()
        if dataset is None:
            raise PermissionError("目标数据集不存在或不属于研究工作空间")
        await DatasetServiceImpl(self.session).verify_dataset_access(dataset_id, str(user_id), str(tenant_id), action="write")
        asset = await self.access.create_asset(
            tenant_id=tenant_id, workspace_id=UUID(str(project.workspace_id)), dataset_id=dataset_id,
            user_id=user_id, source_type="text", title=f"研究报告-{report.id}.md", mime_type="text/markdown",
            metadata={"research_report_id": str(report.id), "review_status": report.review_status}, is_superuser=is_superuser,
        )
        ingestion = await AssetIngestionService(self.session).ingest_bytes(
            asset_id=UUID(str(asset["id"])), tenant_id=tenant_id, user_id=user_id,
            content=report.content_markdown.encode("utf-8"), content_type="text/markdown", is_superuser=is_superuser,
        )
        report.published_dataset_id = dataset.id
        report.published_document_id = UUID(str(ingestion["document_id"])) if ingestion.get("document_id") else None
        await self.session.flush()
        published = await self.get_report(run_id=UUID(str(run.id)), tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser)
        published["published_asset_id"] = asset["id"]
        return published

    async def publish_report_to_knowledge(self, *, report_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, title: str | None = None) -> Optional[dict[str, Any]]:
        result = await self.session.execute(select(ResearchReport).where(ResearchReport.id == str(report_id), ResearchReport.tenant_id == str(tenant_id)))
        report = result.scalar_one_or_none()
        if report is None:
            return None
        run = await self.session.get(ResearchRun, str(report.run_id))
        if run is None:
            return None
        project = await self._get_project(UUID(str(run.project_id)), tenant_id)
        if project is None:
            return None
        await self._verify_project_access(project, tenant_id, user_id, is_superuser)
        if report.review_status != "approved":
            raise ValueError("只有审核通过的报告才能沉淀为知识卡片")
        if report.published_knowledge_item_id:
            return await self.get_report(run_id=UUID(str(run.id)), tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser)
        evidence_result = await self.session.execute(
            select(ResearchEvidence, ResearchSource).join(ResearchSource, ResearchSource.id == ResearchEvidence.source_id).where(ResearchEvidence.run_id == str(run.id))
        )
        evidence_rows = list(evidence_result.all())
        if not evidence_rows:
            raise ValueError("没有可追溯研究证据，不能沉淀知识卡片")
        findings_result = await self.session.execute(select(ResearchFinding.claim).where(ResearchFinding.run_id == str(run.id)))
        conclusions = [str(row[0])[:2000] for row in findings_result.all()]
        knowledge = KnowledgeService(self.session)
        item = await knowledge.create_item(
            tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser,
            workspace_id=UUID(str(project.workspace_id)), title=title or f"研究结论-{project.name}", item_type="conclusion",
            definition=report.content_markdown[:20000], details=report.content_markdown, conclusions=conclusions,
            confidence=0.7, metadata={"research_report_id": str(report.id), "source_count": len(evidence_rows)},
        )
        for evidence, source in evidence_rows:
            await knowledge.add_evidence(
                item_id=UUID(str(item["id"])), tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser,
                research_evidence_id=UUID(str(evidence.id)), quote=evidence.quote, locator=evidence.locator, source_uri=source.source_uri,
            )
        report.published_knowledge_item_id = UUID(str(item["id"]))
        await self.session.flush()
        return await self.get_report(run_id=UUID(str(run.id)), tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser)
