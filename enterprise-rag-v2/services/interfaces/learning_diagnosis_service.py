"""
学习诊断引擎 — 5 阶段学习诊断流水线接口

从 services/interfaces/diagnosis_service.py 复制并字段重映射：
  DiagnosisContext.fault_description → LearningDiagnosisContext.question_text
  DiagnosisContext.fault_code        → LearningDiagnosisContext.kp_code
  DiagnosisContext.equipment_model   → LearningDiagnosisContext.subject_info
  DiagnosisContext.model_id          → LearningDiagnosisContext.subject_id
  DiagnosisContext.dataset_id        → LearningDiagnosisContext.textbook_version_id
  DiagnosisContext.symptoms          → LearningDiagnosisContext.error_tags
"""
from abc import ABC, abstractmethod
from typing import Optional, List, AsyncIterator, Dict, Any
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class StageResult:
    stage: int
    name: str
    status: str = "pending"  # pending / running / done / error
    data: Optional[Any] = None
    elapsed_ms: Optional[int] = None


@dataclass
class LearningDiagnosisContext:
    """学习诊断输入上下文"""
    question_text: str                                    # 错题/题目描述
    kp_code: Optional[str] = None                         # 知识点编码
    subject_info: Optional[str] = None                    # 学科信息
    subject_id: Optional[str] = None                      # 学科ID
    textbook_version_id: Optional[str] = None             # 教材版本ID
    grade_level: Optional[str] = None                     # 年级
    error_tags: Optional[List[str]] = None                # 错题类型标签
    user_id: Optional[str] = None                         # 学生用户ID
    original_images: Optional[List[str]] = None           # 试卷照片
    original_answer: Optional[str] = None                 # 学生答案


class LearningDiagnosisService(ABC):
    """学习诊断服务接口"""

    @property
    @abstractmethod
    def session(self) -> AsyncSession: ...

    @abstractmethod
    async def analyze(self, context: LearningDiagnosisContext) -> dict:
        """执行完整诊断，返回结构化报告"""
        ...

    @abstractmethod
    async def analyze_stream(
        self, context: LearningDiagnosisContext
    ) -> AsyncIterator[str]:
        """流式诊断，yield SSE 事件字符串"""
        ...

    @abstractmethod
    async def get_report(self, report_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    async def list_reports(
        self, user_id: str, page: int = 1, page_size: int = 20
    ) -> dict:
        ...

    @abstractmethod
    async def submit_feedback(self, report_id: str, rating: str, feedback: Optional[str] = None) -> bool:
        ...

    @abstractmethod
    async def start_practice(self, report_id: str, user_id: str) -> Optional[dict]:
        """基于诊断报告生成靶向练习会话"""
        ...

    @abstractmethod
    async def get_practice_session(self, session_id: str) -> Optional[dict]:
        """获取练习会话详情"""
        ...

    @abstractmethod
    async def submit_practice_answer(self, session_id: str, exercise_idx: int, answer: str) -> Optional[dict]:
        """提交练习答案并获取反馈"""
        ...
