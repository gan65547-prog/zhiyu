"""
请求模型定义 - OpenClaw集成接口
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any


class ChatRequest(BaseModel):
    """聊天请求"""
    query: str = Field(..., min_length=1, max_length=2000, description="用户查询内容")
    conversation_id: Optional[str] = Field(None, description="多轮对话上下文ID")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")


class PlatformUserInfo(BaseModel):
    """平台用户信息（用于绑定）"""
    name: Optional[str] = Field(None, description="显示名称")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    tenant_key: Optional[str] = Field(None, description="飞书租户Key")


class BindRequest(BaseModel):
    """用户绑定请求"""
    platform: str = Field(
        ...,
        pattern="^(feishu|wecom|wechat|qq|dingtalk)$",
        description="平台标识"
    )
    platform_user_id: str = Field(..., min_length=1, description="平台用户ID")
    platform_user_info: Optional[PlatformUserInfo] = None
    bind_code: Optional[str] = Field(None, description="绑定码（手动绑定时使用）")
