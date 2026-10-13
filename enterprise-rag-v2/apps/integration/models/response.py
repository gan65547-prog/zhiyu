"""
响应模型定义 - OpenClaw集成接口
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal


class SourceInfo(BaseModel):
    """来源文档信息"""
    document_title: str = Field(..., description="文档标题")
    dataset_name: str = Field(..., description="所属知识库名称")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="相关度评分 (0-1)")
    content_snippet: Optional[str] = Field(None, description="内容摘要")


class QuotaInfo(BaseModel):
    """配额信息"""
    dimension: str = Field(..., description="配额维度名称")
    current: int = Field(..., ge=0, description="当前使用量")
    limit: int = Field(..., ge=0, description="配额上限")
    remaining: int = Field(..., ge=0, description="剩余可用量")
    percentage: float = Field(..., ge=0.0, le=100.0, description="使用百分比")


class SuggestedAction(BaseModel):
    """建议操作（用于升级提示等场景）"""
    type: Literal["upgrade_prompt", "view_usage", "bind_account", "feedback"] = Field(
        ...,
        description="操作类型"
    )
    title: str = Field(..., description="操作标题/按钮文字")
    url: Optional[str] = Field(None, description="跳转链接")


class ChatResponse(BaseModel):
    """聊天响应 (OpenClaw调用的核心返回格式)"""
    success: bool = Field(..., description="是否成功")
    answer: str = Field(..., description="回答内容")
    sources: List[SourceInfo] = Field(default_factory=list, description="来源文档列表")
    conversation_id: Optional[str] = Field(None, description="会话ID（用于多轮对话）")

    # 配额相关字段
    quota_info: Optional[QuotaInfo] = Field(None, description="配额使用情况")
    quota_exceeded: bool = Field(False, description="是否触发配额超限")

    suggested_actions: List[SuggestedAction] = Field(
        default_factory=list,
        description="建议的操作按钮"
    )


class BindResponse(BaseModel):
    """用户绑定响应"""
    success: bool = Field(..., description="是否成功")
    user_id: Optional[int] = Field(None, description="系统用户ID")
    tenant_id: Optional[int] = Field(None, description="租户ID")
    plan: Optional[str] = Field(None, description="历史兼容字段；不控制开源版功能")
    message: str = Field(..., description="提示消息")
    is_new_user: bool = Field(False, description="是否新创建的用户")
    bind_code: Optional[str] = Field(None, description="绑定码（需要手动绑定时）")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: Literal["healthy", "degraded", "unhealthy"] = Field(...)
    version: str = Field(..., description="版本号")
    uptime_seconds: float = Field(..., description="运行时长(秒)")
    services: Dict[str, str] = Field(default_factory=dict, description="各服务状态")
