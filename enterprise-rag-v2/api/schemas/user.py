"""
User API Schemas
用户管理相关的请求和响应模型
"""
from typing import Optional, List, Dict
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr

from .base import BaseResponse, PaginatedResponse
from .tenant import WorkspaceRole


# ============ User Request Models ============

class UserCreateRequest(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=8, description="密码")
    is_active: Optional[bool] = Field(default=True, description="是否激活")
    workspace_ids: Optional[List[str]] = Field(default=None, description="自动加入的工作空间ID列表")
    default_role: Optional[WorkspaceRole] = Field(default=WorkspaceRole.MEMBER, description="默认角色")


class UserUpdateRequest(BaseModel):
    """更新用户请求"""
    username: Optional[str] = Field(None, min_length=2, max_length=50, description="用户名")
    email: Optional[EmailStr] = Field(None, description="邮箱")
    is_active: Optional[bool] = Field(None, description="是否激活")
    workspace_ids: Optional[List[str]] = Field(default=None, description="用户可访问的工作空间ID列表")
    default_role: Optional[WorkspaceRole] = Field(default=WorkspaceRole.MEMBER, description="默认角色")


class UserQueryRequest(BaseModel):
    """用户查询请求"""
    search: Optional[str] = Field(None, description="搜索关键词（用户名/邮箱）")
    is_active: Optional[bool] = Field(None, description="过滤激活状态")
    workspace_id: Optional[str] = Field(None, description="过滤工作空间成员")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(20, ge=1, le=100, description="每页数量")


class UserResetPasswordRequest(BaseModel):
    """重置用户密码请求"""
    new_password: str = Field(..., min_length=8, description="新密码")
    send_email: Optional[bool] = Field(default=False, description="是否发送邮件通知")


class UserActivateRequest(BaseModel):
    """激活/停用用户请求"""
    is_active: bool = Field(..., description="true=激活, false=停用")


# ============ User Response Models ============

class UserWorkspaceInfo(BaseModel):
    """用户工作空间信息"""
    workspace_id: str = Field(..., description="工作空间ID")
    workspace_name: str = Field(..., description="工作空间名称")
    role: WorkspaceRole = Field(..., description="角色")
    is_default: Optional[bool] = Field(default=False, description="是否默认工作空间")
    joined_at: Optional[datetime] = Field(default=None, description="加入时间")


class UserInfo(BaseModel):
    """用户基本信息"""
    id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    is_active: bool = Field(..., description="是否激活")
    is_superuser: bool = Field(..., description="是否超级管理员")
    tenant_id: str = Field(..., description="租户ID")
    current_workspace_id: Optional[str] = Field(default=None, description="当前工作空间ID")
    # 与 list_users /auth/me 一致：可为 ISO 字符串或 None，避免校验失败导致 500
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    updated_at: Optional[datetime] = Field(default=None, description="更新时间")


class UserDetailInfo(UserInfo):
    """用户详细信息"""
    tenant_name: Optional[str] = Field(default=None, description="租户名称")
    current_workspace_name: Optional[str] = Field(default=None, description="当前工作空间名称")
    workspaces: Optional[List[UserWorkspaceInfo]] = Field(default=None, description="用户的工作空间列表")
    extra_metadata: Optional[Dict] = Field(default=None, description="扩展元数据")
    last_login_at: Optional[datetime] = Field(default=None, description="最后登录时间")


class UserCreateResponse(BaseResponse):
    """创建用户响应"""
    data: UserInfo


class UserDetailResponse(BaseResponse):
    """用户详情响应"""
    data: UserDetailInfo


class UserListResponse(PaginatedResponse):
    """用户列表响应"""
    data: List[UserInfo]


class UserDeleteResponse(BaseResponse):
    """删除用户响应"""
    data: Optional[Dict] = None


class UserResetPasswordResponse(BaseResponse):
    """重置密码响应"""
    data: Optional[Dict] = None
    message: str = Field(default="Password reset successfully", description="消息")
    email_sent: bool = Field(default=False, description="邮件是否已发送")


class UserActivateResponse(BaseResponse):
    """激活/停用用户响应"""
    data: UserInfo
