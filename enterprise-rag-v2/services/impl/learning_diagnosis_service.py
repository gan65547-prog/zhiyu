"""
学习诊断引擎实现 — 5 阶段学习诊断流水线

Stage 1: 知识点定位（knowledge_points 表精确+向量匹配）
Stage 2: 教材知识库检索（RAGEngineImpl.query — 教材/教辅/典型例题）
Stage 3: 同类错误案例匹配（learning_error_records 表）
Stage 4: LLM 生成个性化诊断报告（教师辅导 System Prompt）
Stage 5: 保存报告到 learning_diagnosis_reports 表

从 services/impl/diagnosis_service.py 复制骨架，逐阶段替换：
  - 故障码匹配 → 知识点定位
  - 知识库检索 → 教材检索（RAG链路不变，只改查询文本构造）
  - 历史维修案例 → 同类错误案例
  - 设备诊断Prompt → 教师辅导Prompt
"""

import json
import time
from datetime import datetime as _datetime
from typing import Optional, List, AsyncIterator, Dict, Any
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from services.interfaces.learning_diagnosis_service import (
    LearningDiagnosisService, LearningDiagnosisContext, StageResult,
)
from infrastructure.database.models import (
    LearningKnowledgePoint, LearningSubject, LearningTextbookVersion,
    LearningDiagnosisReport, LearningErrorRecord, LearningMaterial, LearningPracticeSession,
)
from infrastructure.logging.logger import get_logger
from services.impl.user_llm_runtime import resolve_user_llm_runtime
from core.rag_config import is_effective_openai_api_key

logger = get_logger(__name__)

# ============================================================
# 学习诊断 System Prompt
# ============================================================

LEARNING_DIAGNOSIS_PROMPT = """你是一位经验丰富的初中数学教师，你的任务是给学生做"错题诊断"。

## 任务
基于学生提供的错题信息、教材内容、同类错误案例，生成一份个性化学习诊断报告。

## 必须按以下 5 个部分输出

### 1. 错误定位
指出学生在哪个具体步骤或概念上出错了。引用教材出处（第X章，涉及的知识点名称）。

### 2. 正确思路
分步骤展示正确的解题过程：
- 每一步说明 WHY（不只是 how）
- 如果有多种解法，列出最高效的一种
- 关键步骤用加粗标注

### 3. 为什么会错
分析最可能的 2-3 个原因，从以下维度判断：
- 概念误区（理解偏差）
- 计算习惯（符号/步骤/单位）
- 审题问题（遗漏条件/误解题意）
引用教材中的相关概念或典型错误类型。

### 4. 下次怎么避免
提供 2-3 条可操作的检查清单：
- 具体到"在哪个步骤检查什么"
- 可以用"如果...就..."的格式

### 5. 掌握度评估
- 评估等级：[未掌握 / 部分掌握 / 基本掌握 / 熟练掌握]
- 一句话后续建议（接下来应该先复习什么，再做什么练习）

## 回答原则
- 严格基于提供的教材内容，不要超出知识库范围
- 所有知识点引用必须标注教材出处
- 不确定的推论标注"（推测）"
- 语气温和鼓励，像老师一对一辅导学生
- 中文输出，数学符号用 LaTeX 格式（如 $x^2 + 3x - 4 = 0$）"""


class LearningDiagnosisServiceImpl(LearningDiagnosisService):
    """学习诊断引擎实现"""

    def __init__(self, session: AsyncSession):
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    # ================================================================
    # Stage 1: 知识点定位
    # ================================================================

    async def _stage1_knowledge_point_match(self, ctx: LearningDiagnosisContext) -> StageResult:
        """在 knowledge_points 表中匹配知识点"""
        t0 = time.monotonic()
        result = StageResult(stage=1, name="知识点定位", status="running")

        if ctx.kp_code:
            # 精确匹配知识点编码
            conditions = [LearningKnowledgePoint.code == ctx.kp_code]
            if ctx.subject_id:
                conditions.append(LearningKnowledgePoint.subject_id == ctx.subject_id)

            query = (
                select(LearningKnowledgePoint)
                .where(*conditions)
                .limit(5)
            )
            exec_result = await self.session.execute(query)
            kps = exec_result.scalars().all()
        else:
            # 模糊匹配：按学科+年级+关键词搜索
            conditions = []
            if ctx.subject_id:
                conditions.append(LearningKnowledgePoint.subject_id == ctx.subject_id)

            query = (
                select(LearningKnowledgePoint)
                .where(*conditions)
                .order_by(LearningKnowledgePoint.difficulty_level)
                .limit(20)
            )
            exec_result = await self.session.execute(query)
            all_kps = exec_result.scalars().all()

            # 用简单的关键词匹配筛选（如果没有向量检索能力，退化为关键词匹配）
            search_terms = ctx.question_text.lower()
            kps = []
            for kp in all_kps:
                if kp.name.lower() in search_terms or any(
                    word in search_terms for word in kp.name.lower().split()
                ):
                    kps.append(kp)
            kps = kps[:5]

        result.status = "done"
        result.data = {
            "matched": len(kps) > 0,
            "count": len(kps),
            "knowledge_points": [
                {
                    "id": str(k.id), "code": k.code, "name": k.name,
                    "chapter": k.chapter, "page_range": k.page_range,
                    "difficulty_level": k.difficulty_level,
                    "prerequisite_kp_ids": k.prerequisite_kp_ids or [],
                }
                for k in kps
            ],
        }
        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        return result

    # ================================================================
    # Stage 2: 教材知识库检索
    # ================================================================

    async def _stage2_textbook_retrieval(self, ctx: LearningDiagnosisContext) -> StageResult:
        """通过 RAG 引擎搜索教材原文 + 教辅解析 + 典型例题"""
        t0 = time.monotonic()
        result = StageResult(stage=2, name="教材检索", status="running")

        # 构建查询文本
        search_query = ctx.question_text
        if ctx.subject_info:
            search_query = f"{ctx.subject_info} {search_query}"

        # 直接查询 learning_materials 表（不依赖 Milvus 向量库的降级方案）
        kps = await self._get_matched_kp_ids(ctx)
        conditions = []
        if kps:
            from sqlalchemy import or_
            conditions.append(
                or_(*[LearningMaterial.knowledge_point_id == kp_id for kp_id in kps[:3]])
            )

        if not conditions:
            result.status = "done"
            result.data = {"searched": True, "count": 0, "documents": []}
            result.elapsed_ms = int((time.monotonic() - t0) * 1000)
            return result

        query = (
            select(LearningMaterial)
            .where(*conditions)
            .order_by(LearningMaterial.content_type)
            .limit(10)
        )
        exec_result = await self.session.execute(query)
        materials = exec_result.scalars().all()

        result.status = "done"
        result.data = {
            "searched": True,
            "count": len(materials),
            "documents": [
                {
                    "content": m.content[:600],
                    "content_type": m.content_type,
                    "title": m.title,
                    "page_number": m.page_number,
                }
                for m in materials
            ],
        }
        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        return result

    async def _get_matched_kp_ids(self, ctx: LearningDiagnosisContext) -> List[str]:
        """获取匹配的知识点ID列表"""
        conditions = []
        if ctx.subject_id:
            conditions.append(LearningKnowledgePoint.subject_id == ctx.subject_id)
        if ctx.kp_code:
            conditions.append(LearningKnowledgePoint.code == ctx.kp_code)

        q = select(LearningKnowledgePoint.id).where(*conditions).limit(10)
        exec_result = await self.session.execute(q)
        return [str(r[0]) for r in exec_result.all()]

    # ================================================================
    # Stage 3: 同类错误案例匹配
    # ================================================================

    async def _stage3_similar_errors_match(self, ctx: LearningDiagnosisContext) -> StageResult:
        """匹配同知识点上的常见错误类型和其他学生的典型错误"""
        t0 = time.monotonic()
        result = StageResult(stage=3, name="错例分析", status="running")

        kp_ids = await self._get_matched_kp_ids(ctx)

        if not kp_ids:
            result.status = "done"
            result.data = {"matched": False, "count": 0, "records": []}
            result.elapsed_ms = int((time.monotonic() - t0) * 1000)
            return result

        from sqlalchemy import or_
        conditions = [
            or_(*[LearningErrorRecord.knowledge_point_id == kp_id for kp_id in kp_ids[:3]])
        ]

        query = (
            select(LearningErrorRecord)
            .where(*conditions)
            .order_by(LearningErrorRecord.frequency.desc())
            .limit(8)
        )
        exec_result = await self.session.execute(query)
        records = exec_result.scalars().all()

        result.status = "done"
        result.data = {
            "matched": len(records) > 0,
            "count": len(records),
            "records": [
                {
                    "id": str(r.id),
                    "error_type": r.error_type,
                    "error_description": r.error_description[:300],
                    "correct_approach": r.correct_approach,
                    "frequency": r.frequency,
                }
                for r in records
            ],
        }
        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        return result

    # ================================================================
    # Stage 4: LLM 生成诊断报告
    # ================================================================

    async def _stage4_llm_generate_report(
        self, ctx: LearningDiagnosisContext, stages: List[StageResult]
    ) -> StageResult:
        """组装上下文 → LLM 生成个性化诊断报告"""
        t0 = time.monotonic()
        result = StageResult(stage=4, name="AI诊断", status="running")

        s1 = stages[0].data if len(stages) > 0 and stages[0].data else {}
        s2 = stages[1].data if len(stages) > 1 and stages[1].data else {}
        s3 = stages[2].data if len(stages) > 2 and stages[2].data else {}

        user_message = f"""## 学生错题信息
学科: {ctx.subject_info or '初中数学'}
年级: {ctx.grade_level or '未指定'}
题目/错题描述: {ctx.question_text}
学生答案: {ctx.original_answer or '未提供'}
错题标签: {', '.join(ctx.error_tags) if ctx.error_tags else '无'}

## 知识点匹配结果
{json.dumps(s1.get('knowledge_points', []), ensure_ascii=False, indent=2) if s1.get('matched') else '未匹配到知识点'}

## 教材相关章节
{json.dumps([d.get('content', '') for d in s2.get('documents', [])], ensure_ascii=False, indent=2) if s2.get('searched') else '未检索到教材内容'}

## 同类错误案例
{json.dumps(s3.get('records', []), ensure_ascii=False, indent=2) if s3.get('matched') else '未找到同类错误案例'}

请基于以上信息，按 5 个部分的格式输出学习诊断报告。"""

        try:
            from core.rag.llm_provider import DeepSeekProvider, OpenAIProvider

            runtime = await resolve_user_llm_runtime(self.session, ctx.user_id)
            if runtime.get("provider") == "openai" and is_effective_openai_api_key(runtime.get("api_key")):
                provider = OpenAIProvider(api_key=runtime["api_key"], model=runtime.get("model"), base_url=runtime.get("base_url"))
            else:
                provider = DeepSeekProvider(api_key=runtime.get("api_key"), model=runtime.get("model"), base_url=runtime.get("base_url"))
            try:
                client = await provider._get_client()
                messages = [
                    {"role": "system", "content": LEARNING_DIAGNOSIS_PROMPT},
                    {"role": "user", "content": user_message},
                ]
                resp = await client.post(
                    f"{provider.base_url}/chat/completions",
                    json={
                        "model": provider.model_name,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 3000,
                        "stream": False,
                    },
                )
                if resp.status_code == 200:
                    body = resp.json()
                    response = body["choices"][0]["message"]["content"]
                else:
                    logger.error(f"[LearningDiagnosis] LLM API error: {resp.status_code} {resp.text}")
                    response = f"LLM调用失败(HTTP {resp.status_code})，请稍后重试"
            finally:
                await provider.close()

            result.status = "done"
            result.data = {"report_text": response}
        except Exception as e:
            logger.error(f"[LearningDiagnosis] Stage4 LLM generation failed: {e}")
            result.status = "error"
            result.data = {"error": str(e)}

        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        return result

    # ================================================================
    # Stage 5: 保存报告
    # ================================================================

    async def _stage5_save_learning_report(
        self, ctx: LearningDiagnosisContext, stages: List[StageResult]
    ) -> StageResult:
        """保存诊断报告到 learning_diagnosis_reports 表"""
        t0 = time.monotonic()
        result = StageResult(stage=5, name="保存报告", status="running")

        try:
            s1_data = stages[0].data if len(stages) > 0 and stages[0].data else {}
            s4_data = stages[3].data if len(stages) > 3 and stages[3].data else {}

            kp_list = s1_data.get("knowledge_points", [])
            weak_kps = [
                {
                    "kp_id": kp.get("id"),
                    "name": kp.get("name"),
                    "difficulty": kp.get("difficulty_level"),
                    "confidence": 0.8,
                }
                for kp in kp_list[:5]
            ]

            # 解析 subject_id: 若未传则默认取"数学"
            subject_id = ctx.subject_id
            if not subject_id:
                subj_result = await self.session.execute(
                    select(LearningSubject).where(LearningSubject.name == "数学").limit(1)
                )
                default_subject = subj_result.scalar_one_or_none()
                subject_id = str(default_subject.id) if default_subject else None

            report = LearningDiagnosisReport(
                id=str(uuid4()),
                user_id=ctx.user_id,
                subject_id=subject_id,
                textbook_version_id=ctx.textbook_version_id,
                grade_level=ctx.grade_level,
                input_type="manual",
                question_text=ctx.question_text,
                original_images=ctx.original_images or [],
                original_answer=ctx.original_answer,
                kp_code=ctx.kp_code,
                error_tags=ctx.error_tags or [],
                weak_knowledge_points=weak_kps,
                error_analysis=[],
                overall_mastery_score=None,
                stage_results={
                    f"stage_{s.stage}": {
                        "name": s.name, "status": s.status,
                        "data": s.data, "elapsed_ms": s.elapsed_ms,
                    }
                    for s in stages
                },
                report_content=s4_data if isinstance(s4_data, dict) else {"report_text": str(s4_data)},
            )
            self.session.add(report)
            await self.session.flush()
            await self.session.refresh(report)
            await self.session.commit()

            result.status = "done"
            result.data = {"report_id": str(report.id)}
        except Exception as e:
            logger.error(f"[LearningDiagnosis] Stage5 save failed: {e}")
            result.status = "error"
            result.data = {"error": str(e)}

        result.elapsed_ms = int((time.monotonic() - t0) * 1000)
        return result

    # ================================================================
    # 完整诊断流水线
    # ================================================================

    async def analyze(self, context: LearningDiagnosisContext) -> dict:
        stages = []

        s1 = await self._stage1_knowledge_point_match(context)
        stages.append(s1)

        s2 = await self._stage2_textbook_retrieval(context)
        stages.append(s2)

        s3 = await self._stage3_similar_errors_match(context)
        stages.append(s3)

        s4 = await self._stage4_llm_generate_report(context, stages)
        stages.append(s4)

        s5 = await self._stage5_save_learning_report(context, stages)
        stages.append(s5)

        # 沉淀错误案例（供后续 Stage3 参考）
        await self._save_to_error_record(context, stages)

        return {
            "report_id": s5.data.get("report_id") if s5.status == "done" else None,
            "overall_mastery_score": None,
            "stage_results": {
                f"stage_{s.stage}": {
                    "name": s.name, "status": s.status,
                    "data": s.data, "elapsed_ms": s.elapsed_ms,
                }
                for s in stages
            },
            "report_content": s4.data if s4.status == "done" else None,
        }

    async def _save_to_error_record(
        self, ctx: LearningDiagnosisContext, stages: List[StageResult]
    ) -> None:
        """将诊断结果沉淀为错误案例记录"""
        try:
            s1_data = stages[0].data if len(stages) > 0 and stages[0].data else {}
            kps = s1_data.get("knowledge_points", [])
            if not kps:
                return

            for error_tag in (ctx.error_tags or ["未分类"]):
                record = LearningErrorRecord(
                    id=str(uuid4()),
                    knowledge_point_id=kps[0].get("id"),
                    error_type=error_tag,
                    error_description=ctx.question_text[:500],
                    correct_approach=None,
                    frequency=1,
                )
                self.session.add(record)
            await self.session.flush()
        except Exception as e:
            logger.warning(f"[LearningDiagnosis] 存入错误案例失败 (非致命): {e}")

    # ================================================================
    # 流式诊断
    # ================================================================

    async def analyze_stream(self, context: LearningDiagnosisContext) -> AsyncIterator[str]:
        import json as _json
        from api.schemas.learning import SSEEvent

        # Stage 1
        yield SSEEvent.stage(1, "知识点定位", "running")
        s1 = await self._stage1_knowledge_point_match(context)
        yield SSEEvent.stage(1, "知识点定位", s1.status)
        yield SSEEvent.progress(0.2)

        # Stage 2
        yield SSEEvent.stage(2, "教材检索", "running")
        s2 = await self._stage2_textbook_retrieval(context)
        yield SSEEvent.stage(2, "教材检索", s2.status)
        if s2.data.get("documents"):
            docs = [{
                "content": d.get("content", "")[:300],
                "title": d.get("title", ""),
            } for d in s2.data["documents"][:3]]
            yield SSEEvent.sources(docs)
        yield SSEEvent.progress(0.5)

        # Stage 3
        yield SSEEvent.stage(3, "错例分析", "running")
        s3 = await self._stage3_similar_errors_match(context)
        yield SSEEvent.stage(3, "错例分析", s3.status)
        yield SSEEvent.progress(0.65)

        # Stage 4 — LLM 流式生成
        yield SSEEvent.stage(4, "AI诊断", "running")

        s1_data = s1.data if s1.data else {}
        s2_data = s2.data if s2.data else {}
        s3_data = s3.data if s3.data else {}

        user_message = f"""## 学生错题信息
学科: {context.subject_info or '初中数学'}
年级: {context.grade_level or '未指定'}
题目/错题描述: {context.question_text}
学生答案: {context.original_answer or '未提供'}
错题标签: {', '.join(context.error_tags) if context.error_tags else '无'}

## 知识点匹配结果
{_json.dumps(s1_data.get('knowledge_points', []), ensure_ascii=False, indent=2) if s1_data.get('matched') else '未匹配到知识点'}

## 教材相关章节
{_json.dumps([d.get('content', '') for d in s2_data.get('documents', [])], ensure_ascii=False, indent=2) if s2_data.get('searched') else '未检索到教材内容'}

## 同类错误案例
{_json.dumps(s3_data.get('records', []), ensure_ascii=False, indent=2) if s3_data.get('matched') else '未找到同类错误案例'}

请基于以上信息，按 5 个部分的格式输出学习诊断报告。"""

        try:
            from core.rag.llm_provider import DeepSeekProvider, OpenAIProvider

            runtime = await resolve_user_llm_runtime(self.session, context.user_id)
            if runtime.get("provider") == "openai" and is_effective_openai_api_key(runtime.get("api_key")):
                provider = OpenAIProvider(api_key=runtime["api_key"], model=runtime.get("model"), base_url=runtime.get("base_url"))
            else:
                provider = DeepSeekProvider(api_key=runtime.get("api_key"), model=runtime.get("model"), base_url=runtime.get("base_url"))
            full_report = ""
            current_section = ""
            try:
                client = await provider._get_client()
                messages = [
                    {"role": "system", "content": LEARNING_DIAGNOSIS_PROMPT},
                    {"role": "user", "content": user_message},
                ]
                async with client.stream(
                    "POST",
                    f"{provider.base_url}/chat/completions",
                    json={
                        "model": provider.model_name,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 3000,
                        "stream": True,
                    },
                ) as resp:
                    if resp.status_code != 200:
                        try:
                            body = await resp.aread()
                            detail = body.decode("utf-8", errors="replace")[:1200]
                        except Exception:
                            detail = getattr(resp, "reason_phrase", None) or ""
                        logger.error(f"[LearningDiagnosis] LLM stream HTTP {resp.status_code}: {detail}")
                        yield SSEEvent.error(f"LLM调用失败 (HTTP {resp.status_code})")
                        full_report = "LLM调用失败，请稍后重试"
                    else:
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                data = line[6:]
                                if data == "[DONE]":
                                    break
                                try:
                                    chunk = _json.loads(data)
                                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        full_report += content
                                        if content.startswith("###"):
                                            current_section = content.strip()
                                        yield SSEEvent.content(current_section or "诊断报告", content)
                                except (_json.JSONDecodeError, KeyError, IndexError):
                                    pass
            finally:
                await provider.close()

            s4 = StageResult(stage=4, name="AI诊断", status="done",
                             data={"report_text": full_report})
        except Exception as e:
            logger.error(f"[LearningDiagnosis] Stage4 stream failed: {e}")
            s4 = StageResult(stage=4, name="AI诊断", status="error", data={"error": str(e)})
            yield SSEEvent.error(f"LLM生成失败: {e}")

        yield SSEEvent.progress(0.95)

        # Stage 5
        yield SSEEvent.stage(5, "保存报告", "running")
        stages_all = [s1, s2, s3, s4]
        s5 = await self._stage5_save_learning_report(context, stages_all)
        yield SSEEvent.stage(5, "保存报告", s5.status)

        # 沉淀错误案例
        await self._save_to_error_record(context, stages_all)

        report_id = s5.data.get("report_id") if s5.status == "done" else None
        yield SSEEvent.done(report_id or "")

    # ================================================================
    # 报告查询
    # ================================================================

    async def get_report(self, report_id: str, user_id: str) -> Optional[dict]:
        result = await self.session.execute(
            select(LearningDiagnosisReport).where(
                LearningDiagnosisReport.id == report_id,
                LearningDiagnosisReport.user_id == user_id,
            )
        )
        r = result.scalar_one_or_none()
        if not r:
            return None
        return {
            "id": str(r.id), "user_id": r.user_id,
            "subject_id": r.subject_id,
            "question_text": r.question_text,
            "error_tags": r.error_tags,
            "weak_knowledge_points": r.weak_knowledge_points,
            "error_analysis": r.error_analysis,
            "stage_results": r.stage_results,
            "report_content": r.report_content,
            "overall_mastery_score": r.overall_mastery_score,
            "rating": r.rating, "feedback": r.feedback,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }

    async def list_reports(self, user_id: str, page: int = 1, page_size: int = 20) -> dict:
        conditions = [LearningDiagnosisReport.user_id == user_id]
        total_result = await self.session.execute(
            select(func.count(LearningDiagnosisReport.id)).where(*conditions)
        )
        total = total_result.scalar()

        offset = (page - 1) * page_size
        result = await self.session.execute(
            select(LearningDiagnosisReport).where(*conditions)
            .order_by(LearningDiagnosisReport.created_at.desc())
            .offset(offset).limit(page_size)
        )
        reports = result.scalars().all()

        return {
            "items": [
                {
                    "id": str(r.id), "subject_id": r.subject_id,
                    "grade_level": r.grade_level,
                    "question_text": r.question_text[:200],
                    "overall_mastery_score": r.overall_mastery_score,
                    "weak_knowledge_points": r.weak_knowledge_points,
                    "rating": r.rating,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in reports
            ],
            "total": total, "page": page, "page_size": page_size,
        }

    async def submit_feedback(
        self, report_id: str, rating: str, feedback: Optional[str], user_id: str
    ) -> bool:
        result = await self.session.execute(
            select(LearningDiagnosisReport).where(
                LearningDiagnosisReport.id == report_id,
                LearningDiagnosisReport.user_id == user_id,
            )
        )
        r = result.scalar_one_or_none()
        if not r:
            return False
        r.rating = rating
        r.feedback = feedback
        await self.session.flush()
        return True

    # ================================================================
    # 靶向练习
    # ================================================================

    PRACTICE_GENERATION_PROMPT = """你是一位经验丰富的教师，需要根据学生的诊断报告生成靶向练习题。

## 任务
基于学生的薄弱知识点，生成 3-5 道针对性练习题。

## 输出格式
每道题用 JSON 数组输出，格式：
```json
[
  {
    "idx": 1,
    "question": "题目描述",
    "answer": "正确答案和完整解题步骤",
    "hints": ["提示1", "提示2"],
    "kp_name": "对应知识点名称",
    "difficulty": "easy|medium|hard"
  }
]
```

## 要求
- 题目难度递进：从基础概念题到综合应用题
- 每道题聚焦一个薄弱知识点
- 提示从模糊到具体，最后一条接近答案但不直接给出
- 中文输出，数学符号用 LaTeX"""

    async def start_practice(self, report_id: str, user_id: str) -> Optional[dict]:
        # 1. 加载诊断报告（仅属主可见）
        result = await self.session.execute(
            select(LearningDiagnosisReport).where(
                LearningDiagnosisReport.id == report_id,
                LearningDiagnosisReport.user_id == user_id,
            )
        )
        report = result.scalar_one_or_none()
        if not report:
            return None

        # 2. 检查是否已有进行中的练习会话
        existing = await self.session.execute(
            select(LearningPracticeSession).where(
                LearningPracticeSession.diagnosis_report_id == report_id,
                LearningPracticeSession.status.in_(["generated", "in_progress"]),
            )
        )
        session = existing.scalar_one_or_none()
        if session:
            return {
                "id": str(session.id),
                "status": session.status,
                "exercises": session.exercises or [],
                "exercises_completed": session.exercises_completed or 0,
                "exercises_correct": session.exercises_correct or 0,
                "diagnosis_report_id": report_id,
            }

        # 3. 获取薄弱知识点信息
        weak_kps = report.weak_knowledge_points or []
        if not weak_kps:
            return None

        kp_names = [kp.get("name", "") for kp in weak_kps[:5]]

        # 4. 调用 LLM 生成练习题
        exercises = []
        try:
            from core.rag.llm_provider import DeepSeekProvider

            user_msg = f"""学生薄弱知识点：
{json.dumps([{"name": kp.get("name"), "difficulty": kp.get("difficulty")} for kp in weak_kps], ensure_ascii=False, indent=2)}

年级: {report.grade_level or '初中'}
原始错题: {report.question_text[:300]}

请生成 3-5 道靶向练习题。只输出 JSON 数组，不要其他文字。"""

            provider = DeepSeekProvider()
            try:
                client = await provider._get_client()
                resp = await client.post(
                    f"{provider.base_url}/chat/completions",
                    json={
                        "model": provider.model_name,
                        "messages": [
                            {"role": "system", "content": self.PRACTICE_GENERATION_PROMPT},
                            {"role": "user", "content": user_msg},
                        ],
                        "temperature": 0.5,
                        "max_tokens": 2000,
                        "stream": False,
                    },
                )
                if resp.status_code == 200:
                    body = resp.json()
                    raw = body["choices"][0]["message"]["content"]
                    raw = raw.strip()
                    if raw.startswith("```"):
                        raw = raw.split("```")[1]
                        if raw.startswith("json"):
                            raw = raw[4:]
                    exercises = json.loads(raw)
                    if not isinstance(exercises, list):
                        exercises = []
                else:
                    logger.error(f"[LearningDiagnosis] Practice LLM error: {resp.status_code}")
            finally:
                await provider.close()
        except Exception as e:
            logger.error(f"[LearningDiagnosis] Practice generation failed: {e}")

        # 降级：如果 LLM 失败，用简单模板生成
        if not exercises:
            for i, kp in enumerate(weak_kps[:3]):
                exercises.append({
                    "idx": i + 1,
                    "question": f"请简述知识点「{kp.get('name', '未知')}」的核心概念，并举一个例子说明。",
                    "answer": "根据教材内容回答，教师将根据你的答案评估掌握程度。",
                    "hints": ["回顾教材相关章节", "回忆课堂上老师讲解的例子"],
                    "kp_name": kp.get("name", ""),
                    "difficulty": "easy",
                })

        # 5. 保存练习会话
        kp_ids = [kp.get("kp_id") for kp in weak_kps[:5]]
        session = LearningPracticeSession(
            id=str(uuid4()),
            diagnosis_report_id=report_id,
            user_id=user_id,
            knowledge_point_ids=kp_ids,
            exercises=exercises,
            answers_submitted=[],
            exercises_completed=0,
            exercises_correct=0,
            mastery_before=report.overall_mastery_score,
            status="generated",
        )
        self.session.add(session)
        await self.session.flush()
        await self.session.commit()

        return {
            "id": str(session.id),
            "status": session.status,
            "exercises": exercises,
            "exercises_completed": 0,
            "exercises_correct": 0,
            "diagnosis_report_id": report_id,
        }

    async def get_practice_session(self, session_id: str, user_id: str) -> Optional[dict]:
        result = await self.session.execute(
            select(LearningPracticeSession).where(
                LearningPracticeSession.id == session_id,
                LearningPracticeSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            return None
        return {
            "id": str(session.id),
            "diagnosis_report_id": session.diagnosis_report_id,
            "knowledge_point_ids": session.knowledge_point_ids,
            "exercises": session.exercises or [],
            "answers_submitted": session.answers_submitted or [],
            "exercises_completed": session.exercises_completed or 0,
            "exercises_correct": session.exercises_correct or 0,
            "mastery_before": session.mastery_before,
            "mastery_after": session.mastery_after,
            "status": session.status,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "created_at": session.created_at.isoformat() if session.created_at else None,
        }

    async def submit_practice_answer(
        self, session_id: str, exercise_idx: int, answer: str, user_id: str
    ) -> Optional[dict]:
        result = await self.session.execute(
            select(LearningPracticeSession).where(
                LearningPracticeSession.id == session_id,
                LearningPracticeSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            return None

        exercises = list(session.exercises or [])
        answers = list(session.answers_submitted or [])

        # 找到对应题目
        ex = next((e for e in exercises if e.get("idx") == exercise_idx), None)
        if not ex:
            return None

        # 简单判断正确性（基于答案关键词匹配）
        correct_answer = ex.get("answer", "")
        is_correct = len(answer) > 5 and (
            answer.strip().lower() in correct_answer.lower()
            or any(word in correct_answer for word in answer.strip()[:10])
        )

        answers.append({
            "idx": exercise_idx,
            "answer": answer,
            "correct": is_correct,
            "submitted_at": _datetime.utcnow().isoformat(),
        })

        session.answers_submitted = answers
        session.exercises_completed = len({a["idx"] for a in answers})
        session.exercises_correct = sum(1 for a in answers if a.get("correct"))
        session.status = "in_progress"
        if session.exercises_completed >= len(exercises):
            session.status = "completed"
            session.completed_at = _datetime.utcnow()

        await self.session.flush()
        await self.session.commit()

        return {
            "correct": is_correct,
            "correct_answer": correct_answer,
            "encouragement": "回答正确，继续加油！" if is_correct else "还有提升空间，看看正确答案的思路吧",
            "exercises_completed": session.exercises_completed,
            "exercises_correct": session.exercises_correct,
            "status": session.status,
        }
