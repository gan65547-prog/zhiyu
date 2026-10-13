"""
基础Schema定义

定义通用的请求和响应模型
"""

from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from uuid import UUID

T = TypeVar('T')


class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool = Field(True, description="请求是否成功")
    message: Optional[str] = Field(None, description="响应消息")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="响应时间戳")


class DataResponse(BaseResponse, Generic[T]):
    """数据响应模型"""
    data: T = Field(..., description="响应数据")


class ErrorResponse(BaseResponse):
    """错误响应模型"""
    success: bool = Field(False, description="请求失败")
    error_code: str = Field(..., description="错误代码")
    error_detail: Optional[Any] = Field(None, description="错误详情")


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class PaginatedResponse(BaseResponse, Generic[T]):
    """分页响应模型"""
    data: List[T] = Field(..., description="数据列表")
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total_pages: int = Field(..., description="总页数")
    has_next: bool = Field(..., description="是否有下一页")
    has_prev: bool = Field(..., description="是否有上一页")


class IDResponse(BaseModel):
    """ID响应模型"""
    id: UUID = Field(..., description="资源ID")


class StatusResponse(BaseModel):
    """状态响应模型"""
    status: str = Field(..., description="状态")
    message: Optional[str] = Field(None, description="状态消息")