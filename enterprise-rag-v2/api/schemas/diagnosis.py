"""
诊断 Schema — 故障诊断请求/响应/SSE事件
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


class DiagnosisRequest(BaseModel):
    """诊断请求"""
    fault_description: str = Field(..., min_length=1, description="故障现象描述")
    fault_code: Optional[str] = Field(None, max_length=50, description="故障码")
    equipment_model: Optional[str] = Field(None, max_length=200, description="设备型号（品牌+型号）")
    model_id: Optional[str] = Field(None, description="系统内置设备型号ID")
    dataset_id: Optional[str] = Field(None, description="关联知识库ID（用于RAG检索）")
    symptoms: Optional[List[str]] = Field(None, description="症状标签列表")
    equipment_instance_id: Optional[str] = Field(None, description="关联设备实例ID")


class StageResult(BaseModel):
    """单个阶段的诊断结果"""
    stage: int = Field(..., description="阶段编号 1-5")
    name: str = Field(..., description="阶段名称")
    status: str = Field("pending", description="pending/running/done/error")
    data: Optional[Any] = None
    elapsed_ms: Optional[int] = None


class DiagnosisResponse(BaseModel):
    """诊断响应（完整报告）"""
    id: str
    tenant_id: str
    severity: Optional[str] = None
    report_content: Optional[dict] = None
    stage_results: dict
    created_at: datetime


class DiagnosisFeedback(BaseModel):
    """诊断反馈"""
    report_id: str
    rating: str = Field(..., pattern="^(useful|useless)$")
    feedback: Optional[str] = Field(None, max_length=1000)


# ============================================================
# SSE 事件类型
# ============================================================

class SSEEvent:
    """SSE 流式事件结构（非 Pydantic，用于手动构造 SSE 字符串）"""

    @staticmethod
    def stage(stage_num: int, name: str, status: str):
        """阶段状态变更事件"""
        import json
        return f"event: stage\ndata: {json.dumps({'stage': stage_num, 'name': name, 'status': status})}\n\n"

    @staticmethod
    def progress(percent: float):
        """进度事件"""
        import json
        return f"event: progress\ndata: {json.dumps({'percent': percent})}\n\n"

    @staticmethod
    def content(section: str, text: str):
        """内容流式输出事件"""
        import json
        return f"event: content\ndata: {json.dumps({'section': section, 'text': text})}\n\n"

    @staticmethod
    def sources(docs: list):
        """引用来源事件"""
        import json
        return f"event: sources\ndata: {json.dumps({'documents': docs})}\n\n"

    @staticmethod
    def error(message: str):
        """错误事件"""
        import json
        return f"event: error\ndata: {json.dumps({'message': message})}\n\n"

    @staticmethod
    def done(report_id: str):
        """完成事件"""
        import json
        return f"event: done\ndata: {json.dumps({'report_id': report_id})}\n\n"


import json  # noqa: E402 — ensure json is importable for static methods above
