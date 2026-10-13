"""
学习诊断 API — SSE 流式诊断端点

从 api/routers/diagnosis.py 复制并改造：
  - 路由前缀: /api/v1/learning
  - 依赖: get_current_active_user（复用B端认证）
  - 服务: LearningDiagnosisServiceImpl
"""
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_active_user, get_db
from api.schemas.base import DataResponse
from api.schemas.learning import LearningDiagnosisRequest, LearningDiagnosisFeedback, PracticeAnswerSubmit
from services.interfaces.learning_diagnosis_service import LearningDiagnosisContext
from services.impl.learning_diagnosis_service import LearningDiagnosisServiceImpl
from infrastructure.logging.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


async def _resolve_learning_context(
    request: LearningDiagnosisRequest,
    user_id: str,
) -> LearningDiagnosisContext:
    """解析学习诊断上下文"""
    return LearningDiagnosisContext(
        question_text=request.question_text,
        kp_code=request.kp_code,
        subject_info=request.subject_info,
        subject_id=request.subject_id,
        textbook_version_id=request.textbook_version_id,
        grade_level=request.grade_level,
        error_tags=request.error_tags,
        user_id=user_id,
        original_images=request.original_images,
        original_answer=request.original_answer,
    )


@router.get("/subjects", response_model=DataResponse)
async def list_learning_subjects(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """列出所有学科"""
    from sqlalchemy import select
    from infrastructure.database.models import LearningSubject
    result = await db.execute(select(LearningSubject).order_by(LearningSubject.sort_order))
    subjects = result.scalars().all()
    items = [{"id": str(s.id), "name": s.name, "grade_level": s.grade_level} for s in subjects]
    return DataResponse(success=True, data={"items": items, "total": len(items)})


@router.post("/analyze", response_model=DataResponse)
async def analyze_learning(
    request: LearningDiagnosisRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """提交错题信息，返回完整诊断报告"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法确定用户身份")

    svc = LearningDiagnosisServiceImpl(db)
    ctx = await _resolve_learning_context(request, str(user_id))
    result = await svc.analyze(ctx)
    return DataResponse(success=True, message="诊断完成", data=result)


@router.post("/analyze/stream")
async def analyze_learning_stream(
    request: LearningDiagnosisRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """SSE 流式诊断 — 每个阶段实时推送进度、内容和来源"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法确定用户身份")

    svc = LearningDiagnosisServiceImpl(db)
    ctx = await _resolve_learning_context(request, str(user_id))

    async def event_stream():
        async for event_str in svc.analyze_stream(ctx):
            yield event_str

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/reports", response_model=DataResponse)
async def list_learning_reports(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """历史诊断报告列表"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法确定用户身份")

    svc = LearningDiagnosisServiceImpl(db)
    result = await svc.list_reports(str(user_id), page, page_size)
    return DataResponse(success=True, data=result)


@router.get("/reports/{report_id}", response_model=DataResponse)
async def get_learning_report(
    report_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """诊断报告详情"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法确定用户身份")

    svc = LearningDiagnosisServiceImpl(db)
    report = await svc.get_report(report_id, str(user_id))
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报告不存在")
    return DataResponse(success=True, data=report)


@router.post("/feedback", response_model=DataResponse)
async def submit_learning_feedback(
    request: LearningDiagnosisFeedback,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """诊断报告评分反馈"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法确定用户身份")

    svc = LearningDiagnosisServiceImpl(db)
    success = await svc.submit_feedback(request.report_id, request.rating, request.feedback, str(user_id))
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报告不存在")
    return DataResponse(success=True, message="感谢反馈", data=None)


@router.post("/reports/{report_id}/start-practice", response_model=DataResponse)
async def start_practice(
    report_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """基于诊断报告生成靶向练习会话"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法确定用户身份")

    svc = LearningDiagnosisServiceImpl(db)
    session = await svc.start_practice(report_id, str(user_id))
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="报告不存在或无可练习知识点")
    return DataResponse(success=True, message="练习已生成", data=session)


@router.get("/practice/{session_id}", response_model=DataResponse)
async def get_practice_session(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """获取练习会话详情"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法确定用户身份")

    svc = LearningDiagnosisServiceImpl(db)
    session = await svc.get_practice_session(session_id, str(user_id))
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="练习会话不存在")
    return DataResponse(success=True, data=session)


@router.post("/practice/{session_id}/submit", response_model=DataResponse)
async def submit_practice_answer(
    session_id: str,
    request: PracticeAnswerSubmit,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
):
    """提交练习答案"""
    user_id = current_user.get("sub") or current_user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法确定用户身份")

    svc = LearningDiagnosisServiceImpl(db)
    result = await svc.submit_practice_answer(session_id, request.exercise_idx, request.answer, str(user_id))
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="练习会话或题目不存在")
    return DataResponse(success=True, data=result)
