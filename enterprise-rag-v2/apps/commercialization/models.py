from typing import Optional
from pydantic import BaseModel


# ========== 错误响应模型 ==========
class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict] = None


class QuotaExceededResponse(ErrorResponse):
    """自托管资源上限响应。"""
    dimension: str
    dimension_label: str
    current: int
    limit: int
    percentage: float


# ========== 自定义异常类 ==========
class QuotaExceededError(Exception):
    """租户达到部署管理员配置的资源上限时抛出。"""

    # 维度中文标签映射
    DIMENSION_LABELS = {
        "documents": "文档数量",
        "users": "用户数",
        "storage_mb": "存储空间",
        "api_calls_monthly": "API调用次数",
        "api_calls_per_day": "每日API调用次数",
        "chat_messages_monthly": "AI对话次数",
        "chat_messages_per_day": "每日AI对话次数",
        "workspaces": "工作空间数",
        "research_runs_monthly": "研究运行次数",
        "research_sources_monthly": "研究来源数量",
        "research_output_tokens_monthly": "研究输出 token",
    }

    def __init__(self, dimension: str, current: int, limit: int):
        self.dimension = dimension
        self.current = current
        self.limit = limit
        self.dimension_label = self.DIMENSION_LABELS.get(dimension, dimension)
        message = f"{self.dimension_label}配额已达上限 ({current}/{limit})"
        self.message = message
        super().__init__(message)

    def to_response_dict(self) -> dict:
        """转换为API响应字典（含完整升级提示）"""
        return {
            "error": "QUOTA_EXCEEDED",
            "code": 403,
        "message": f"{self.dimension_label}已达到自托管部署设置的资源上限 ({self.current}/{self.limit})",
            "dimension": self.dimension,
            "dimension_label": self.dimension_label,
            "current": self.current,
            "limit": self.limit,
            "percentage": round(self.current / self.limit * 100, 1) if self.limit > 0 else 100,
        }
