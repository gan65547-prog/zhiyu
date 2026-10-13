"""
Chat API Schemas
对话和RAG查询相关的请求和响应模型
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

from .base import BaseResponse, PaginatedResponse


class MessageRole(str, Enum):
    """消息角色枚举"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class RetrievalMode(str, Enum):
    """检索模式枚举"""
    SEMANTIC = "semantic"  # 语义检索
    KEYWORD = "keyword"  # 关键词检索
    HYBRID = "hybrid"  # 混合检索


class ConversationVisibilityEnum(str, Enum):
    """会话可见性级别枚举"""
    PRIVATE = "private"  # 私有：只有创建者和超级管理员可访问
    WORKSPACE = "workspace"  # 工作空间共享：工作空间成员可访问
    TENANT = "tenant"  # 租户级别：租户内所有用户可访问


# ============ Request Models ============

class ChatMessage(BaseModel):
    """聊天消息"""
    role: MessageRole = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[datetime] = Field(None, description="时间戳")


class ChatRequest(BaseModel):
    """对话请求"""
    dataset_id: str = Field(..., description="数据集ID")
    query: str = Field(..., min_length=1, max_length=2000, description="用户查询")
    conversation_id: Optional[str] = Field(None, description="会话ID")
    history: Optional[List[ChatMessage]] = Field(default=None, description="历史消息")
    retrieval_mode: RetrievalMode = Field(RetrievalMode.HYBRID, description="检索模式")
    top_k: int = Field(5, ge=1, le=20, description="返回top-k个相关文档")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="生成温度")
    max_tokens: int = Field(2000, ge=100, le=4000, description="最大生成token数")
    stream: bool = Field(False, description="是否流式返回")


class ConversationCreateRequest(BaseModel):
    """创建会话请求（支持可见性设置）"""
    dataset_id: str = Field(..., description="数据集ID")
    title: Optional[str] = Field(None, description="会话标题")
    metadata: Optional[dict] = Field(default=None, description="元数据")
    visibility: Optional[ConversationVisibilityEnum] = Field(
        default=ConversationVisibilityEnum.PRIVATE,
        description="会话可见性级别（默认私有）"
    )
    workspace_id: Optional[str] = Field(None, description="工作空间ID（可选）")


class ConversationUpdateRequest(BaseModel):
    """更新会话请求（支持可见性变更）"""
    title: Optional[str] = Field(None, description="会话标题")
    metadata: Optional[dict] = Field(None, description="元数据")
    visibility: Optional[ConversationVisibilityEnum] = Field(
        None,
        description="新的可见性级别（可选）"
    )


class ConversationQueryRequest(BaseModel):
    """会话查询请求（支持权限过滤）"""
    dataset_id: Optional[str] = Field(None, description="数据集ID")
    keyword: Optional[str] = Field(None, description="关键词搜索")
    visibility: Optional[ConversationVisibilityEnum] = Field(None, description="按可见性过滤")
    workspace_id: Optional[str] = Field(None, description="按工作空间过滤")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class AdminConversationQueryRequest(BaseModel):
    """管理员会话查询请求（高级过滤）"""
    user_id: Optional[str] = Field(None, description="按创建者过滤")
    workspace_id: Optional[str] = Field(None, description="按工作空间过滤")
    visibility: Optional[ConversationVisibilityEnum] = Field(None, description="按可见性过滤")
    start_date: Optional[datetime] = Field(None, description="开始日期")
    end_date: Optional[datetime] = Field(None, description="结束日期")
    keyword: Optional[str] = Field(None, description="关键词搜索")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


# ============ Response Models ============

class RetrievedChunk(BaseModel):
    """检索到的文档块"""
    chunk_id: str = Field(..., description="文档块ID")
    document_id: str = Field(..., description="文档ID")
    document_name: str = Field(..., description="文档名称")
    content: str = Field(..., description="文档块内容")
    score: float = Field(..., description="相似度分数")
    metadata: dict = Field(default_factory=dict, description="元数据")


class ChatResponseData(BaseModel):
    """对话响应数据"""
    conversation_id: str = Field(..., description="会话ID")
    message_id: str = Field(..., description="消息ID")
    answer: str = Field(..., description="回答内容")
    retrieved_chunks: List[RetrievedChunk] = Field(default_factory=list, description="检索到的文档块")
    tokens_used: int = Field(..., description="使用的token数")
    retrieval_time_ms: int = Field(..., description="检索耗时(毫秒)")
    generation_time_ms: int = Field(..., description="生成耗时(毫秒)")
    metadata: dict = Field(default_factory=dict, description="元数据")


class ChatResponse(BaseResponse):
    """对话响应"""
    data: ChatResponseData


class StreamChunk(BaseModel):
    """流式响应块"""
    conversation_id: str = Field(..., description="会话ID")
    message_id: str = Field(..., description="消息ID")
    delta: str = Field(..., description="增量内容")
    finish_reason: Optional[str] = Field(None, description="结束原因")


class ConversationInfo(BaseModel):
    """会话信息（支持权限管理）"""
    id: str = Field(..., description="会话ID")
    dataset_id: str = Field(..., description="数据集ID")
    user_id: str = Field(..., description="创建者用户ID")
    title: str = Field(..., description="会话标题")
    visibility: ConversationVisibilityEnum = Field(..., description="会话可见性级别")
    workspace_id: Optional[str] = Field(None, description="工作空间ID")
    message_count: int = Field(0, description="消息数量")
    metadata: dict = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class ConversationCreateResponse(BaseResponse):
    """创建会话响应"""
    data: ConversationInfo


class ConversationDetailResponse(BaseResponse):
    """会话详情响应"""
    data: ConversationInfo


class ConversationListResponse(PaginatedResponse):
    """会话列表响应"""
    data: List[ConversationInfo]


class ConversationDeleteResponse(BaseResponse):
    """删除会话响应"""
    data: dict = Field(default_factory=lambda: {"deleted": True})


# ============ Message History Models ============

class MessageInfo(BaseModel):
    """消息信息"""
    id: str = Field(..., description="消息ID")
    conversation_id: str = Field(..., description="会话ID")
    role: MessageRole = Field(..., description="消息角色")
    content: str = Field(..., description="消息内容")
    retrieved_chunks: Optional[List[RetrievedChunk]] = Field(None, description="检索到的文档块")
    tokens_used: Optional[int] = Field(None, description="使用的token数")
    created_at: datetime = Field(..., description="创建时间")


class MessageHistoryResponse(BaseResponse):
    """消息历史响应"""
    data: List[MessageInfo]
