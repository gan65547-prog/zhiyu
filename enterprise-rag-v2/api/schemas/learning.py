"""
学习诊断 Schema — 诊断请求/响应/SSE事件

从 api/schemas/diagnosis.py 复制并字段重映射：
  fault_description → question_text
  fault_code        → kp_code
  equipment_model   → subject_info
  model_id          → subject_id
  dataset_id        → textbook_version_id
  symptoms          → error_tags
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime

# SSEEvent 直接从 diagnosis schema 导入复用
from api.schemas.diagnosis import SSEEvent  # noqa: F401 — 复用SSE事件类型


class LearningDiagnosisRequest(BaseModel):
    """学习诊断请求"""
    question_text: str = Field(..., min_length=1, description="错题/题目描述")
    kp_code: Optional[str] = Field(None, max_length=50, description="知识点编码（可选，用于精确定位）")
    subject_info: Optional[str] = Field(None, max_length=200, description="学科信息（名称+年级）")
    subject_id: Optional[str] = Field(None, description="学科ID")
    textbook_version_id: Optional[str] = Field(None, description="教材版本ID")
    grade_level: Optional[str] = Field(None, description="年级")
    error_tags: Optional[List[str]] = Field(None, description="错题类型标签列表")
    original_images: Optional[List[str]] = Field(None, description="试卷/错题照片URLs")
    original_answer: Optional[str] = Field(None, description="学生的错误答案")


class StageResult(BaseModel):
    """单个阶段的诊断结果"""
    stage: int = Field(..., description="阶段编号 1-5")
    name: str = Field(..., description="阶段名称")
    status: str = Field("pending", description="pending/running/done/error")
    data: Optional[Any] = None
    elapsed_ms: Optional[int] = None


class LearningDiagnosisResponse(BaseModel):
    """诊断响应"""
    id: str
    user_id: str
    subject_id: str
    overall_mastery_score: Optional[int] = None
    report_content: Optional[dict] = None
    stage_results: dict
    created_at: datetime


class LearningDiagnosisFeedback(BaseModel):
    """诊断反馈"""
    report_id: str
    rating: str = Field(..., pattern="^(useful|useless)$")
    feedback: Optional[str] = Field(None, max_length=1000)


class PracticeAnswerSubmit(BaseModel):
    """练习答案提交"""
    exercise_idx: int
    answer: str
