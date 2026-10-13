"""
Tenant API Schemas
租户和工作空间相关的请求和响应模型
"""
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from enum import Enum

from .base import BaseResponse, PaginatedResponse


class TenantStatus(str, Enum):
    """租户状态枚举"""
    ACTIVE = "active"  # 活跃
    SUSPENDED = "suspended"  # 暂停
    DELETED = "deleted"  # 已删除


class WorkspaceRole(str, Enum):
    """工作空间角色枚举"""
    OWNER = "owner"  # 所有者
    ADMIN = "admin"  # 管理员
    MEMBER = "member"  # 成员
    VIEWER = "viewer"  # 查看者


class SubscriptionPlan(str, Enum):
    """数据库兼容用的历史计划值；不授予任何功能档位。"""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# ============ Tenant Request Models ============

class TenantCreateRequest(BaseModel):
    """创建租户请求"""
    name: str = Field(..., min_length=1, max_length=100, description="租户名称")
    contact_email: EmailStr = Field(..., description="联系邮箱")
    contact_phone: Optional[str] = Field(None, description="联系电话")
    metadata: Optional[dict] = Field(default=None, description="元数据")
    # 初始管理员信息
    admin_username: str = Field(..., min_length=2, max_length=50, description="管理员用户名")
    admin_email: EmailStr = Field(..., description="管理员邮箱")
    admin_password: str = Field(..., min_length=8, description="管理员密码")


class TenantUpdateRequest(BaseModel):
    """更新租户请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="租户名称")
    contact_email: Optional[EmailStr] = Field(None, description="联系邮箱")
    contact_phone: Optional[str] = Field(None, description="联系电话")
    status: Optional[TenantStatus] = Field(None, description="租户状态")
    metadata: Optional[dict] = Field(None, description="元数据")
    plan: Optional[SubscriptionPlan] = Field(None, description="历史兼容字段；开源版不允许修改")


class TenantQueryRequest(BaseModel):
    """租户查询请求"""
    status: Optional[TenantStatus] = Field(None, description="租户状态")
    keyword: Optional[str] = Field(None, description="关键词搜索")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


# ============ Workspace Request Models ============

class WorkspaceCreateRequest(BaseModel):
    """创建工作空间请求"""
    name: str = Field(..., min_length=1, max_length=100, description="工作空间名称")
    description: Optional[str] = Field(None, max_length=500, description="描述")
    metadata: Optional[dict] = Field(default=None, description="元数据")


class WorkspaceUpdateRequest(BaseModel):
    """更新工作空间请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="工作空间名称")
    description: Optional[str] = Field(None, max_length=500, description="描述")
    metadata: Optional[dict] = Field(None, description="元数据")


class WorkspaceQueryRequest(BaseModel):
    """工作空间查询请求"""
    keyword: Optional[str] = Field(None, description="关键词搜索")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class WorkspaceMemberAddRequest(BaseModel):
    """添加工作空间成员请求"""
    user_id: str = Field(..., description="用户ID")
    role: WorkspaceRole = Field(WorkspaceRole.MEMBER, description="角色")


class WorkspaceMemberUpdateRequest(BaseModel):
    """更新工作空间成员请求"""
    role: WorkspaceRole = Field(..., description="角色")


# ============ Tenant Response Models ============

class TenantQuota(BaseModel):
    """租户配额"""
    max_workspaces: int = Field(..., description="最大工作空间数")
    max_users: int = Field(..., description="最大用户数")
    max_datasets: int = Field(..., description="最大数据集数")
    max_documents: int = Field(..., description="最大文档数")
    max_storage_gb: int = Field(..., description="最大存储空间(GB)")
    max_api_calls_per_day: int = Field(..., description="每日最大API调用次数")


class TenantUsage(BaseModel):
    """租户使用情况"""
    workspace_count: int = Field(..., description="工作空间数")
    user_count: int = Field(..., description="用户数")
    dataset_count: int = Field(..., description="数据集数")
    document_count: int = Field(..., description="文档数")
    storage_used_gb: float = Field(..., description="已使用存储空间(GB)")
    api_calls_today: int = Field(..., description="今日API调用次数")


class TenantAdminInfo(BaseModel):
    """租户管理员信息"""
    id: str = Field(..., description="管理员ID")
    username: str = Field(..., description="管理员用户名")
    email: str = Field(..., description="管理员邮箱")


class TenantInfo(BaseModel):
    """租户信息"""
    id: str = Field(..., description="租户ID")
    name: str = Field(..., description="租户名称")
    contact_email: str = Field(..., description="联系邮箱")
    contact_phone: Optional[str] = Field(None, description="联系电话")
    plan: SubscriptionPlan = Field(..., description="历史兼容字段，不控制开源版功能")
    status: TenantStatus = Field(..., description="租户状态")
    quota: TenantQuota = Field(..., description="配额")
    usage: TenantUsage = Field(..., description="使用情况")
    admin_info: Optional[TenantAdminInfo] = Field(None, description="初始管理员信息")
    metadata: dict = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class TenantCreateResponse(BaseResponse):
    """创建租户响应"""
    data: TenantInfo


class TenantDetailResponse(BaseResponse):
    """租户详情响应"""
    data: TenantInfo


class TenantListResponse(PaginatedResponse):
    """租户列表响应"""
    data: List[TenantInfo]


class TenantDeleteResponse(BaseResponse):
    """删除租户响应"""
    data: dict = Field(default_factory=lambda: {"deleted": True})


# ============ Workspace Response Models ============

class WorkspaceInfo(BaseModel):
    """工作空间信息"""
    id: str = Field(..., description="工作空间ID")
    tenant_id: str = Field(..., description="租户ID")
    name: str = Field(..., description="工作空间名称")
    description: Optional[str] = Field(None, description="描述")
    is_default: bool = Field(False, description="是否默认工作空间")
    member_count: int = Field(0, description="成员数量")
    dataset_count: int = Field(0, description="数据集数量")
    metadata: dict = Field(default_factory=dict, description="元数据")
    # 服务层可能返回 isoformat 字符串或 None（历史数据），避免响应模型校验失败导致 500
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")


class WorkspaceCreateResponse(BaseResponse):
    """创建工作空间响应"""
    data: WorkspaceInfo


class WorkspaceDetailResponse(BaseResponse):
    """工作空间详情响应"""
    data: WorkspaceInfo


class WorkspaceListResponse(PaginatedResponse):
    """工作空间列表响应"""
    data: List[WorkspaceInfo]


class WorkspaceDeleteResponse(BaseResponse):
    """删除工作空间响应"""
    data: dict = Field(default_factory=lambda: {"deleted": True})


class WorkspaceSwitchResponse(BaseResponse):
    """切换工作空间响应"""
    data: WorkspaceInfo


# ============ Workspace Member Models ============

class WorkspaceUserInfo(BaseModel):
    """工作空间成员用户信息"""
    id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")


class WorkspaceMemberInfo(BaseModel):
    """工作空间成员信息"""
    id: str = Field(..., description="成员ID")
    workspace_id: str = Field(..., description="工作空间ID")
    user_id: str = Field(..., description="用户ID")
    role: WorkspaceRole = Field(..., description="角色")
    user: Optional[WorkspaceUserInfo] = Field(None, description="用户信息")
    joined_at: datetime = Field(..., description="加入时间")


class WorkspaceMemberListResponse(BaseResponse):
    """工作空间成员列表响应"""
    data: List[WorkspaceMemberInfo]


class WorkspaceMemberAddResponse(BaseResponse):
    """添加工作空间成员响应"""
    data: WorkspaceMemberInfo


class WorkspaceMemberRemoveResponse(BaseResponse):
    """移除工作空间成员响应"""
    data: dict = Field(default_factory=lambda: {"removed": True})
