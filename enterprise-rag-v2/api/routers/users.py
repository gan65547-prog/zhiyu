"""
用户管理API路由

提供用户管理相关的HTTP接口
"""

from typing import Annotated, Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    get_db,
    get_current_active_user,
    require_tenant_admin,
    require_user_access,
    get_user_service,
    get_pagination,
)
from api.schemas.user import (
    UserCreateRequest,
    UserUpdateRequest,
    UserResetPasswordRequest,
    UserActivateRequest,
    UserListResponse,
    UserCreateResponse,
    UserDetailResponse,
    UserResetPasswordResponse,
    UserActivateResponse,
    UserInfo,
    UserDetailInfo
)
from services.interfaces.user_service import UserService
from core.exceptions import ResourceConflictError, ResourceNotFoundError, ValidationError
from infrastructure.logging.logger import get_logger

router = APIRouter(tags=["users"])
logger = get_logger(__name__)


@router.get("", response_model=UserListResponse)
async def list_users(
    current_user: Annotated[dict, Depends(get_current_active_user)],
    _: Annotated[None, Depends(require_tenant_admin)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    pagination: Annotated[dict, Depends(get_pagination)],
    search: Optional[str] = Query(None, description="搜索关键词"),
    is_active: Optional[bool] = Query(None, description="过滤激活状态"),
    workspace_id: Optional[str] = Query(None, description="过滤工作空间成员"),
    tenant_id_param: Optional[str] = Query(None, alias="tenant_id", description="指定租户ID（仅超级管理员）")
):
    """获取当前租户的用户列表"""
    # 超级管理员可以通过参数指定租户ID
    if current_user.get("is_superuser") and tenant_id_param:
        try:
            tenant_id = UUID(str(tenant_id_param).strip())
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的 tenant_id 参数",
            )
    else:
        raw_tid = current_user.get("tenant_id")
        if not raw_tid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not associated with any tenant",
            )
        try:
            tenant_id = UUID(str(raw_tid).strip())
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的租户信息，请重新登录",
            )
    
    # 调用服务层
    page = await user_service.list_users(
        tenant_id=tenant_id,
        page=pagination["page"],
        page_size=pagination["page_size"],
        search=search,
        is_active=is_active,
        workspace_id=UUID(workspace_id) if workspace_id else None
    )
    
    # 计算分页信息
    total_pages = (page.total + page.page_size - 1) // page.page_size
    has_next = page.page < total_pages
    has_prev = page.page > 1
    
    return UserListResponse(
        success=True,
        data=[UserInfo(**item) for item in page.items],
        total=page.total,
        page=page.page,
        page_size=page.page_size,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.post("", response_model=UserCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    _: Annotated[None, Depends(require_tenant_admin)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    tenant_id_param: Optional[str] = Query(None, alias="tenant_id", description="指定租户ID（仅超级管理员）")
):
    """创建新用户"""
    # 超级管理员可以通过参数指定租户ID
    if current_user.get("is_superuser") and tenant_id_param:
        try:
            tenant_id = UUID(str(tenant_id_param).strip())
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的 tenant_id 参数",
            )
    else:
        raw_tid = current_user.get("tenant_id")
        if not raw_tid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not associated with any tenant",
            )
        try:
            tenant_id = UUID(str(raw_tid).strip())
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无效的租户信息，请重新登录",
            )
    
    try:
        # 转换 workspace_ids
        workspace_ids = None
        if request.workspace_ids:
            try:
                workspace_ids = [UUID(wid) for wid in request.workspace_ids]
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid workspace ID format: {str(e)}"
                )
        
        user_data = await user_service.create_user(
            tenant_id=tenant_id,
            username=request.username,
            email=request.email,
            password=request.password,
            is_active=request.is_active,
            workspace_ids=workspace_ids,
            default_role=request.default_role
        )
        
        return UserCreateResponse(
            success=True,
            data=UserInfo(**user_data)
        )
    except ResourceConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to create user: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建用户失败"
        )


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(
    user_id: str,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """获取用户详情"""
    # 简单的权限检查（临时方案）
    is_self = current_user["sub"] == user_id
    is_admin = False
    
    # 检查是否为租户管理员
    try:
        from api.deps import require_tenant_admin
        await require_tenant_admin(current_user, db)
        is_admin = True
    except HTTPException:
        pass
    
    if not (is_self or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限访问此用户信息"
        )
    
    try:
        user_data = await user_service.get_user(UUID(user_id))
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        return UserDetailResponse(
            success=True,
            data=UserDetailInfo(**user_data)
        )
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to get user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户详情失败"
        )


@router.put("/{user_id}", response_model=UserDetailResponse)
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """更新用户信息"""
    # 简单的权限检查（临时方案）
    is_self = current_user["sub"] == user_id
    is_admin = False
    
    # 检查是否为租户管理员
    try:
        from api.deps import require_tenant_admin
        await require_tenant_admin(current_user, db)
        is_admin = True
    except HTTPException:
        pass
    
    if not (is_self or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限访问此用户信息"
        )
    
    try:
        # 用户本人不能修改 is_active
        if is_self and request.is_active is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您不能修改自己的激活状态"
            )
        
        # 转换 workspace_ids
        update_data = request.model_dump(exclude_unset=True)
        if 'workspace_ids' in update_data and update_data['workspace_ids']:
            try:
                update_data['workspace_ids'] = [UUID(wid) for wid in update_data['workspace_ids']]
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid workspace ID format: {str(e)}"
                )
        
        user_data = await user_service.update_user(
            UUID(user_id),
            **update_data
        )
        
        # 获取完整的用户详情
        full_user = await user_service.get_user(UUID(user_id))
        
        return UserDetailResponse(
            success=True,
            data=UserDetailInfo(**full_user)
        )
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    except ResourceConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to update user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户失败"
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    _: Annotated[None, Depends(require_tenant_admin)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    """删除用户（软删除，标记为非激活）"""
    # 不能删除自己
    if current_user["sub"] == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="您不能删除自己"
        )
    
    try:
        await user_service.delete_user(UUID(user_id))
        return None
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to delete user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除用户失败"
        )


@router.post("/{user_id}/reset-password", response_model=UserResetPasswordResponse)
async def reset_password(
    user_id: str,
    request: UserResetPasswordRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    _: Annotated[None, Depends(require_tenant_admin)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    """重置用户密码"""
    try:
        result = await user_service.reset_password(
            UUID(user_id),
            request.new_password,
            request.send_email
        )
        
        return UserResetPasswordResponse(
            success=True,
            message=result["message"],
            email_sent=result["email_sent"]
        )
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to reset password for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="重置密码失败"
        )


@router.put("/{user_id}/activate", response_model=UserActivateResponse)
async def activate_user(
    user_id: str,
    request: UserActivateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    _: Annotated[None, Depends(require_tenant_admin)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    """激活/停用用户"""
    # 不能停用自己
    if current_user["sub"] == user_id and not request.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="您不能停用自己"
        )
    
    try:
        user_data = await user_service.activate_user(
            UUID(user_id),
            request.is_active
        )
        
        # 获取完整的用户信息
        full_user = await user_service.get_user(UUID(user_id))
        
        return UserActivateResponse(
            success=True,
            data=UserInfo(**full_user)
        )
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to activate user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户状态失败"
        )


@router.get("/{user_id}/workspaces")
async def get_user_workspaces(
    user_id: str,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """获取用户的工作空间列表"""
    # 简单的权限检查（临时方案）
    is_self = current_user["sub"] == user_id
    is_admin = False
    
    # 检查是否为租户管理员
    try:
        from api.deps import require_tenant_admin
        await require_tenant_admin(current_user, db)
        is_admin = True
    except HTTPException:
        pass
    
    if not (is_self or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限访问此用户信息"
        )
    
    try:
        workspaces = await user_service.get_user_workspaces(UUID(user_id))
        return {
            "success": True,
            "data": workspaces
        }
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to get user workspaces for %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户工作空间失败"
        )
