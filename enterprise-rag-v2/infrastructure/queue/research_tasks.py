"""研究运行异步执行器。

首版先完成可追溯证据包：所有输出都绑定 ResearchSource/Evidence，未配置分析模型时不编造结论。
"""

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
import httpx
from databases import Database

from infrastructure.database.models import (
    Asset,
    Document,
    DocumentChunk,
    ResearchEvidence,
    ResearchFinding,
    ResearchReport,
    ResearchRun,
    ResearchSample,
    ResearchSource,
    ResearchQuestion,
    ResearchProject,
    AgentRun, AgentSchedule,
)
from infrastructure.database.session import AsyncSessionLocal
from infrastructure.logging.logger import get_logger
from infrastructure.queue.celery_app import celery_app
from infrastructure.queue.celery_asyncio import run_coroutine
from core.interfaces.rag_engine import RetrievedDocument
from core.rag.llm_provider import DeepSeekProvider, OllamaLLMProvider, OpenAIProvider
from core.rag_config import get_rag_config, is_effective_openai_api_key
from core.config import get_settings
from infrastructure.cache import get_cache
from apps.commercialization.services.quota_service import QuotaService
from services.impl.safe_fetcher import SafeFetcher
from services.impl.external_search import ExternalSearchProvider, ExternalSearchUnavailable
from services.impl.agent_runtime_service import AgentRuntimeService, next_schedule_time
from services.impl.research_service import ResearchService
from services.impl.research_topic_service import ResearchTopicService
from services.impl.user_llm_runtime import resolve_user_llm_runtime


logger = get_logger("infrastructure.queue.research_tasks")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _chunks_for_document(session, document_id: str, limit: int = 5):
    result = await session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index.asc()).limit(limit)
    )
    return list(result.scalars().all())


async def _add_document_source(session, run: ResearchRun, document: Document, asset: Asset | None = None) -> list[tuple[ResearchSource, str]]:
    source = ResearchSource(
        tenant_id=run.tenant_id, workspace_id=run.workspace_id, run_id=run.id,
        asset_id=asset.id if asset else None, source_uri=asset.source_uri if asset else None,
        title=document.file_name, status="available", captured_at=_utcnow(),
    )
    session.add(source)
    await session.flush()
    pairs = []
    for chunk in await _chunks_for_document(session, str(document.id)):
        evidence = ResearchEvidence(
            tenant_id=run.tenant_id, workspace_id=run.workspace_id, run_id=run.id,
            source_id=source.id, quote=chunk.content[:4000], locator=f"chunk:{chunk.chunk_index}", created_at=_utcnow(),
        )
        session.add(evidence)
        pairs.append((source, chunk.content[:4000]))
    return pairs


async def _add_url_source(session, run: ResearchRun, url: str, title: str | None = None) -> list[tuple[ResearchSource, str]]:
    fetched = await SafeFetcher(max_bytes=int((run.limits or {}).get("max_source_bytes", 20 * 1024 * 1024))).fetch(url)
    content = fetched.content.decode("utf-8", errors="replace")[:10000]
    source = ResearchSource(
        tenant_id=run.tenant_id, workspace_id=run.workspace_id, run_id=run.id,
        source_uri=fetched.url, title=title or fetched.url, content_hash=hashlib.sha256(fetched.content).hexdigest(),
        status="available", captured_at=_utcnow(),
    )
    session.add(source)
    await session.flush()
    session.add(ResearchEvidence(
        tenant_id=run.tenant_id, workspace_id=run.workspace_id, run_id=run.id,
        source_id=source.id, quote=content, locator="url:body", created_at=_utcnow(),
    ))
    return [(source, content)]


async def _collect_sample_sources(session, run: ResearchRun) -> list[tuple[ResearchSource, str]]:
    result = await session.execute(select(ResearchSample).where(ResearchSample.project_id == run.project_id))
    samples = list(result.scalars().all())
    source_pairs: list[tuple[ResearchSource, str]] = []
    for sample in samples:
        if sample.asset_id:
            asset = await session.get(Asset, str(sample.asset_id))
            if asset and asset.legacy_document_id:
                document = await session.get(Document, str(asset.legacy_document_id))
                if document:
                    source_pairs.extend(await _add_document_source(session, run, document, asset))
        elif sample.dataset_id:
            documents_result = await session.execute(
                select(Document).where(Document.dataset_id == str(sample.dataset_id)).order_by(Document.created_at.desc()).limit(3)
            )
            for document in documents_result.scalars().all():
                source_pairs.extend(await _add_document_source(session, run, document))
        elif sample.source_uri:
            source_pairs.extend(await _add_url_source(session, run, sample.source_uri))
    return source_pairs


async def _collect_external_sources(session, run: ResearchRun) -> list[tuple[ResearchSource, str]]:
    project_result = await session.execute(select(ResearchProject).where(ResearchProject.id == str(run.project_id)))
    project = project_result.scalar_one_or_none()
    configured_search = (project.extra_metadata or {}).get("external_search", {}) if project else {}
    search_config = configured_search if isinstance(configured_search, dict) else {}
    queries = search_config.get("queries", [])
    source_pairs: list[tuple[ResearchSource, str]] = []
    enabled = search_config.get("enabled") is True and isinstance(queries, list) and bool(queries)
    status = {"enabled": enabled, "queries": len(queries) if isinstance(queries, list) else 0, "attempted": 0, "failed": 0, "source_count": 0, "fallback": "internal"}
    _set_source_collection_status(run, status)
    if enabled:
        provider = ExternalSearchProvider(max_results=int(search_config.get("max_results", 5)))
        for query in queries[:5]:
            status["attempted"] += 1
            try:
                for result in await provider.search(str(query)):
                    source_pairs.extend(await _add_url_source(session, run, result.url, result.title))
            except (ExternalSearchUnavailable, ValueError, OSError, httpx.HTTPError) as exc:
                status["failed"] += 1
                logger.warning("外部搜索失败，继续使用内部来源 query=%s error=%s", query, exc)
            status["source_count"] = len(source_pairs)
            _set_source_collection_status(run, status)
    return source_pairs


async def _collect_sources(session, run: ResearchRun) -> list[tuple[ResearchSource, str]]:
    max_sources = int((run.limits or {}).get("max_sources", 50))
    source_pairs = await _collect_sample_sources(session, run)
    if len(source_pairs) < max_sources:
        source_pairs.extend(await _collect_external_sources(session, run))
    return source_pairs[:max_sources]


def _set_source_collection_status(run: ResearchRun, status: dict[str, Any]) -> None:
    """把外部检索是否降级写入运行计划，供报告和工作台解释结果来源。"""
    if status.get("failed", 0) > 0:
        status["fallback"] = "internal"
    elif status.get("source_count", 0) > 0:
        status["fallback"] = "none"
    plan = dict(run.plan or {})
    plan["source_collection"] = dict(status)
    run.plan = plan


async def _cancelled_since_last_checkpoint(session, run: ResearchRun) -> bool:
    """在长阶段之间读取最新状态，避免取消后的 worker 覆盖终态。"""
    status = await session.scalar(
        select(ResearchRun.status).where(
            ResearchRun.id == str(run.id),
            ResearchRun.tenant_id == str(run.tenant_id),
        )
    )
    if status != "cancelled":
        return False
    # 采集阶段可能已经创建了未提交的来源/证据；取消时一并丢弃本批次的中间写入。
    await session.rollback()
    return True


async def _build_findings(session, run: ResearchRun, source_pairs: list[tuple[ResearchSource, str]]) -> tuple[list[ResearchFinding], list[str], list[dict]]:
    findings = []
    topic_clusters = ResearchTopicService.cluster(source_pairs)
    report_lines = ["# 研究证据报告", "", "> 当前版本生成的是可追溯证据包，未配置分析模型时不会自动推断结论。", ""]
    if topic_clusters:
        report_lines.extend(["## 主题分布（规则化聚类）", ""])
        report_lines.extend(f"- {item['topic']}：覆盖 {item['source_count']} 个来源" for item in topic_clusters)
        report_lines.append("")
    for index, (source, quote) in enumerate(source_pairs, 1):
        evidence_result = await session.execute(
            select(ResearchEvidence).where(ResearchEvidence.source_id == source.id).order_by(ResearchEvidence.created_at.desc()).limit(1)
        )
        evidence = evidence_result.scalar_one_or_none()
        if evidence is None:
            continue
        finding = ResearchFinding(
            tenant_id=run.tenant_id, workspace_id=run.workspace_id, run_id=run.id,
            claim=f"来源 {index} 提供了待分析材料摘录，需结合研究问题进行人工或模型分析。",
            claim_type="observation", confidence=0.3, evidence_ids=[str(evidence.id)], needs_review=True,
            review_status="pending", created_at=_utcnow(),
        )
        session.add(finding)
        report_lines.extend([f"## 来源 {index}: {source.title or source.source_uri or '未命名来源'}", "", quote[:4000], "", f"证据 ID: `{evidence.id}`", ""])
        findings.append(finding)
    return findings, report_lines, topic_clusters


async def _store_report(session, run: ResearchRun, findings: list[ResearchFinding], report_lines: list[str], source_count: int, input_chars: int, topic_clusters: list[dict], model_name: str | None = None) -> None:
    existing = await session.scalar(select(ResearchReport).where(ResearchReport.run_id == str(run.id)))
    if existing is not None:
        return
    report = ResearchReport(
        tenant_id=run.tenant_id, workspace_id=run.workspace_id, run_id=run.id,
        version=1, content_markdown="\n".join(report_lines),
        content_json={
            "finding_count": len(findings),
            "source_count": source_count,
            "estimated_input_chars": input_chars,
            "topic_clusters": topic_clusters,
            "max_output_tokens": int((run.limits or {}).get("max_output_tokens", 3000)),
            "evidence_only": model_name is None,
            "source_collection": dict((run.plan or {}).get("source_collection") or {}),
        },
        model_name=model_name, prompt_version="research-v1" if model_name else None, citation_completeness=1.0 if findings else 0.0,
        review_status="draft", created_at=_utcnow(), updated_at=_utcnow(),
    )
    session.add(report)


async def _clear_retry_artifacts(session, run: ResearchRun) -> None:
    """重试同一研究运行时清理上一次不完整产物，保持运行级幂等。"""
    await session.execute(delete(ResearchReport).where(ResearchReport.run_id == str(run.id)))
    await session.execute(delete(ResearchFinding).where(ResearchFinding.run_id == str(run.id)))
    await session.execute(delete(ResearchEvidence).where(ResearchEvidence.run_id == str(run.id)))
    await session.execute(delete(ResearchSource).where(ResearchSource.run_id == str(run.id)))


async def _synthesize_with_configured_model(session, run: ResearchRun, source_pairs: list[tuple[ResearchSource, str]]) -> tuple[str | None, str | None, list[str]]:
    if run is None:
        return None, None, []
    config = get_rag_config()
    runtime = await resolve_user_llm_runtime(session, str(run.created_by))
    runtime_api_key = runtime.get("api_key")
    explicitly_enabled = os.getenv("RESEARCH_ENABLE_LLM", "").lower() == "true"
    if not is_effective_openai_api_key(runtime_api_key) and not is_effective_openai_api_key(config.deepseek_api_key) and not explicitly_enabled:
        return None, None, []
    documents = [
        RetrievedDocument(
            id=str(source.id), content=quote, metadata={"source_id": str(source.id), "source_uri": source.source_uri},
            score=1.0, document_id=str(source.id), document_name=source.title or "研究来源", chunk_index=0,
        )
        for source, quote in source_pairs
    ]
    questions_result = await session.execute(
        select(ResearchQuestion.question).where(ResearchQuestion.project_id == str(run.project_id)).order_by(ResearchQuestion.sort_order.asc())
    )
    questions = [row[0] for row in questions_result.all()]
    question = "；".join(questions) if questions else "请总结这些研究来源"
    if is_effective_openai_api_key(runtime_api_key) and runtime.get("provider") == "openai":
        provider = OpenAIProvider(api_key=runtime_api_key, model=runtime.get("model"), base_url=runtime.get("base_url"))
    elif is_effective_openai_api_key(runtime_api_key) or is_effective_openai_api_key(config.deepseek_api_key):
        provider = DeepSeekProvider(api_key=runtime_api_key, model=runtime.get("model"), base_url=runtime.get("base_url"))
    else:
        provider = OllamaLLMProvider()
    prompt = f"研究主题：{question}\n请基于来源内容输出研究摘要，所有事实必须能回溯来源，无法确认的内容标注待审核。"
    try:
        answer = await provider.generate(prompt, documents, temperature=0.2, max_tokens=int((run.limits or {}).get("max_output_tokens", 3000)))
    except Exception:
        logger.exception("研究模型综合失败，降级为证据包 run_id=%s", run.id)
        return None, None, []
    model_name = getattr(provider, "model_name", provider.__class__.__name__)
    evidence_result = await session.execute(
        select(ResearchEvidence.id).where(ResearchEvidence.run_id == str(run.id))
    )
    evidence_ids = [str(row[0]) for row in evidence_result.all()]
    return answer, model_name, evidence_ids


async def _run_research_async(run_id: str, tenant_id: str) -> dict:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ResearchRun).where(ResearchRun.id == run_id, ResearchRun.tenant_id == tenant_id))
        run = result.scalar_one_or_none()
        if run is None:
            raise LookupError("研究运行不存在")
        if run.status == "cancelled":
            return {"run_id": run_id, "status": "cancelled"}
        if run.status == "completed":
            return {"run_id": run_id, "status": "completed"}
        agent_result = await session.execute(select(AgentRun).where(AgentRun.research_run_id == str(run.id)))
        agent_run = agent_result.scalar_one_or_none()
        runtime = AgentRuntimeService(session)
        try:
            if run.retry_count > 0:
                await _clear_retry_artifacts(session, run)
            run.status, run.current_stage, run.progress, run.started_at = "searching", "collecting_sources", 10, _utcnow()
            if agent_run:
                agent_run.status, agent_run.current_step, agent_run.progress, agent_run.started_at = "running", "collect_sources", 10, _utcnow()
                await runtime.mark_step(agent_run_id=agent_run.id, step_key="collect_sources", status="running")
            await session.commit()
            if await _cancelled_since_last_checkpoint(session, run):
                return {"run_id": run_id, "status": "cancelled"}
            source_pairs = await _collect_sources(session, run)
            if await _cancelled_since_last_checkpoint(session, run):
                return {"run_id": run_id, "status": "cancelled"}
            if not source_pairs:
                raise ValueError("研究没有可用来源，请先完成素材解析或添加可访问 URL")
            if agent_run:
                await runtime.mark_step(agent_run_id=agent_run.id, step_key="collect_sources", status="completed", output={"source_count": len(source_pairs)})
                await runtime.mark_step(agent_run_id=agent_run.id, step_key="build_evidence", status="running")
            run.current_stage, run.progress = "building_evidence", 60
            await session.flush()
            findings, report_lines, topic_clusters = await _build_findings(session, run, source_pairs)
            if await _cancelled_since_last_checkpoint(session, run):
                return {"run_id": run_id, "status": "cancelled"}
            if agent_run:
                await runtime.mark_step(agent_run_id=agent_run.id, step_key="build_evidence", status="completed", output={"finding_count": len(findings)})
                await runtime.mark_step(agent_run_id=agent_run.id, step_key="synthesize_findings", status="running")
            synthesis, model_name, evidence_ids = await _synthesize_with_configured_model(session, run, source_pairs)
            if await _cancelled_since_last_checkpoint(session, run):
                return {"run_id": run_id, "status": "cancelled"}
            if synthesis:
                synthesis_finding = ResearchFinding(
                    tenant_id=run.tenant_id, workspace_id=run.workspace_id, run_id=run.id,
                    claim=synthesis, claim_type="synthesis", confidence=0.6,
                    evidence_ids=evidence_ids, needs_review=True, review_status="pending", created_at=_utcnow(),
                )
                session.add(synthesis_finding)
                findings.append(synthesis_finding)
                report_lines[3:3] = ["## 模型综合（待审核）", "", synthesis, ""]
            if agent_run:
                await runtime.mark_step(agent_run_id=agent_run.id, step_key="synthesize_findings", status="completed", output={"model_name": model_name, "synthesized": bool(synthesis)})
                await runtime.mark_step(agent_run_id=agent_run.id, step_key="generate_report", status="running")
            await session.flush()
            if await _cancelled_since_last_checkpoint(session, run):
                return {"run_id": run_id, "status": "cancelled"}
            run.status, run.current_stage, run.progress, run.completed_at = "completed", "completed", 100, _utcnow()
            await _store_report(session, run, findings, report_lines, len(source_pairs), sum(len(quote) for _, quote in source_pairs), topic_clusters, model_name)
            if agent_run:
                await runtime.mark_step(agent_run_id=agent_run.id, step_key="generate_report", status="completed", output={"report_status": "draft"})
                await runtime.request_approval(agent_run_id=agent_run.id, step_key="human_review")
                agent_run.status, agent_run.current_step, agent_run.progress = "waiting_approval", "human_review", 90
            await session.commit()
            return {"run_id": run_id, "status": run.status, "source_count": len(source_pairs)}
        except Exception as exc:
            run.status, run.current_stage, run.error_message = "failed", "failed", str(exc)[:2000]
            if agent_run:
                agent_run.status, agent_run.current_step, agent_run.error_message = "failed", "failed", str(exc)[:2000]
                await session.flush()
            await session.commit()
            logger.exception("研究运行失败 run_id=%s", run_id)
            raise


@celery_app.task(name="research.run", bind=True, max_retries=1, default_retry_delay=30)
def run_research_task(self, run_id: str, tenant_id: str) -> dict:
    try:
        return run_coroutine(_run_research_async(run_id, tenant_id))
    except (ConnectionError, TimeoutError) as exc:
        raise self.retry(exc=exc)


async def _dispatch_due_schedules_async() -> int:
    """Beat 只投递到队列；事务锁和 next_run_at 推进避免重复投递。"""
    now = _utcnow()
    dispatched = []
    quota_db = Database(get_settings().database.url)
    await quota_db.connect()
    try:
        quota_service = QuotaService(quota_db, await get_cache())
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(AgentSchedule).where(
                    AgentSchedule.enabled.is_(True), AgentSchedule.next_run_at <= now,
                ).with_for_update(skip_locked=True).limit(50)
            )
            for schedule in result.scalars().all():
                try:
                    run = await ResearchService(session, quota_service=quota_service).create_run(
                        project_id=UUID(str(schedule.project_id)), tenant_id=UUID(str(schedule.tenant_id)),
                        user_id=UUID(str(schedule.created_by)), is_superuser=True, limits=schedule.config_json or {},
                    )
                    schedule.last_run_at = now
                    schedule.last_run_id = run["id"]
                    schedule.last_error = None
                    schedule.next_run_at = next_schedule_time(schedule.schedule_expression, now)
                    dispatched.append((str(run["id"]), str(schedule.tenant_id)))
                except Exception as exc:
                    schedule.last_error = str(exc)[:2000]
                    schedule.next_run_at = now + timedelta(minutes=5)
                    logger.exception("Agent 调度投递失败 schedule_id=%s", schedule.id)
            await session.commit()
    finally:
        await quota_db.disconnect()
    for run_id, tenant_id in dispatched:
        run_research_task.delay(run_id, tenant_id)
    return len(dispatched)


@celery_app.task(name="agent.dispatch_due_schedules")
def dispatch_due_schedules() -> int:
    return run_coroutine(_dispatch_due_schedules_async())
