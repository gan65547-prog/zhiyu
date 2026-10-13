"""
认证相关Schema定义

定义认证API的请求和响应模型
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime


# ============ 请求模型 ============

class UserRegister(BaseModel):
    """用户注册请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    name: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "name": "张三",
                "password": "SecurePass123!"
            }
        }


class UserLogin(BaseModel):
    """用户登录请求"""
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., description="密码")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!"
            }
        }


class RefreshTokenRequest(BaseModel):
    """刷新Token请求"""
    refresh_token: Optional[str] = Field(None, description="刷新令牌")


class PasswordChange(BaseModel):
    """修改密码请求"""
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")


# ============ 响应模型 ============

class UserResponse(BaseModel):
    """用户信息响应"""
    id: UUID = Field(..., description="用户ID")
    email: EmailStr = Field(..., description="邮箱地址")
    name: str = Field(..., description="用户名")
    avatar: Optional[str] = Field(None, description="头像URL")
    status: str = Field(..., description="用户状态")
    created_at: datetime = Field(..., description="创建时间")
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token响应"""
    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field("Bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")
    user: UserResponse = Field(..., description="用户信息")


class TokenPayload(BaseModel):
    """Token载荷"""
    sub: UUID = Field(..., description="用户ID")
    tenant_id: Optional[UUID] = Field(None, description="租户ID")
    workspace_id: Optional[UUID] = Field(None, description="工作空间ID")
    exp: datetime = Field(..., description="过期时间")