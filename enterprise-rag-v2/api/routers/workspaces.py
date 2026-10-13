"""
工作空间路由

处理工作空间管理相关的API端点
"""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from api.schemas.tenant import (
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
    WorkspaceQueryRequest,
    WorkspaceInfo,
    WorkspaceMemberInfo,
    WorkspaceMemberAddRequest,
    WorkspaceMemberUpdateRequest,
    WorkspaceCreateResponse,
    WorkspaceDetailResponse,
    WorkspaceListResponse,
    WorkspaceDeleteResponse,
    WorkspaceMemberListResponse,
    WorkspaceMemberAddResponse,
    WorkspaceMemberRemoveResponse,
    WorkspaceSwitchResponse,
)
from api.deps import (
    get_workspace_service,
    get_tenant_service,
    get_current_active_user,
    get_auth_service,
    get_tenant_id,
)
from apps.commercialization.models import QuotaExceededError
from services.interfaces.workspace_service import WorkspaceService
from services.interfaces.auth_service import AuthService
from core.value_objects.pagination import Pagination
from infrastructure.logging.logger import get_logger


router = APIRouter()
logger = get_logger(__name__)


@router.get("/current", response_model=WorkspaceDetailResponse)
async def get_current_workspace(
    current_user: Annotated[dict, Depends(get_current_active_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)]
):
    """获取当前用户的工作空间"""
    user_id = UUID(current_user["sub"])
    tenant_id = current_user.get("tenant_id")
    
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户缺少租户信息")
    
    result = await workspace_service.get_current_workspace(
        user_id, tenant_id=str(tenant_id) if tenant_id else None
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="当前用户没有关联的工作空间"
        )
    return WorkspaceDetailResponse(success=True, data=WorkspaceInfo(**result))


@router.post("/{workspace_id}/switch", response_model=WorkspaceSwitchResponse)
async def switch_workspace(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)]
):
    """切换用户当前工作空间"""
    try:
        user_id = UUID(current_user["sub"])
        
        result = await workspace_service.switch_workspace(
            workspace_id=workspace_id,
            user_id=user_id
        )
        return WorkspaceSwitchResponse(
            success=True,
            message="工作空间切换成功",
            data=WorkspaceInfo(**result)
        )
    except ValueError as e:
        # 判断是否是权限错误
        if "不是工作空间成员" in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to switch workspace: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="切换工作空间失败"
        )


@router.post("/", response_model=WorkspaceCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: WorkspaceCreateRequest,
    tenant_id: Annotated[UUID, Depends(get_tenant_id)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)]
):
    """创建工作空间"""
    try:
        user_id = UUID(current_user["sub"])
        result = await workspace_service.create_workspace(
            tenant_id=tenant_id,
            name=request.name,
            creator_id=user_id,
            description=request.description,
            metadata=request.metadata
        )
        return WorkspaceCreateResponse(
            success=True,
            message="Workspace created successfully",
            data=WorkspaceInfo(**result)
        )
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.to_response_dict()
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to create workspace: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create workspace")


@router.get("/{workspace_id}", response_model=WorkspaceDetailResponse)
async def get_workspace(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)]
):
    """获取工作空间详情（验证用户是否是成员）"""
    user_id = UUID(current_user["sub"])
    result = await workspace_service.get_workspace_with_member_check(workspace_id, user_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found or access denied")
    
    return WorkspaceDetailResponse(success=True, data=WorkspaceInfo(**result))


@router.put("/{workspace_id}", response_model=WorkspaceDetailResponse)
async def update_workspace(
    workspace_id: UUID,
    request: WorkspaceUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """更新工作空间"""
    try:
        # 验证workspace属于用户的租户
        workspace = await workspace_service.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        
        tenant_id = current_user.get("tenant_id")
        if workspace.get("tenant_id") != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您无权修改该工作空间（跨租户访问被拒绝）"
            )
        
        # 验证用户是否有编辑权限
        user_id = UUID(current_user["sub"])
        has_permission = await auth_service.verify_permission(
            user_id=user_id,
            resource_type="workspace",
            resource_id=workspace_id,
            action="edit"
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您无权修改该工作空间（权限不足）"
            )
        
        update_data = request.model_dump(exclude_unset=True)
        result = await workspace_service.update_workspace(workspace_id, **update_data)
        return WorkspaceDetailResponse(success=True, data=WorkspaceInfo(**result))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to update workspace: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update workspace")


@router.delete("/{workspace_id}", response_model=WorkspaceDeleteResponse)
async def delete_workspace(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """删除工作空间"""
    # 验证workspace属于用户的租户
    workspace = await workspace_service.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    
    tenant_id = current_user.get("tenant_id")
    if workspace.get("tenant_id") != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您无权删除该工作空间（跨租户访问被拒绝）"
        )
    
    # 验证用户是否有删除权限
    user_id = UUID(current_user["sub"])
    has_permission = await auth_service.verify_permission(
        user_id=user_id,
        resource_type="workspace",
        resource_id=workspace_id,
        action="delete"
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您无权删除该工作空间（权限不足）"
        )
    
    success = await workspace_service.delete_workspace(workspace_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return WorkspaceDeleteResponse(success=True, message="Workspace deleted successfully")


@router.get("/", response_model=WorkspaceListResponse)
async def list_workspaces(
    tenant_id: Annotated[UUID, Depends(get_tenant_id)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    keyword: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """查询工作空间列表（仅用户是成员的）"""
    user_id = UUID(current_user["sub"])
    pagination = Pagination(page=page, page_size=page_size)
    result = await workspace_service.list_workspaces(
        tenant_id=tenant_id,
        user_id=user_id,
        keyword=keyword,
        pagination=pagination
    )

    items = [WorkspaceInfo(**item) for item in result.items]
    return WorkspaceListResponse(
        success=True,
        data=items,
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        total_pages=result.total_pages,
        has_next=result.has_next,
        has_prev=result.has_prev
    )


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberAddResponse, status_code=status.HTTP_201_CREATED)
async def add_workspace_member(
    workspace_id: UUID,
    request: WorkspaceMemberAddRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """添加工作空间成员"""
    try:
        # 验证workspace属于用户的租户
        workspace = await workspace_service.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        
        tenant_id = current_user.get("tenant_id")
        if workspace.get("tenant_id") != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您无权管理该工作空间的成员（跨租户访问被拒绝）"
            )
        
        # 验证用户是否有管理成员权限
        user_id = UUID(current_user["sub"])
        has_permission = await auth_service.verify_permission(
            user_id=user_id,
            resource_type="workspace",
            resource_id=workspace_id,
            action="manage_members"
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您无权管理该工作空间的成员（权限不足）"
            )
        # 验证用户ID格式
        try:
            user_id = UUID(request.user_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid user ID format: {str(e)}"
            )
        
        result = await workspace_service.add_member(
            workspace_id=workspace_id,
            user_id=user_id,
            role=request.role.value
        )
        return WorkspaceMemberAddResponse(
            success=True,
            message="Member added successfully",
            data=WorkspaceMemberInfo(**result)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to add workspace member: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add member")


@router.get("/{workspace_id}/members", response_model=WorkspaceMemberListResponse)
async def list_workspace_members(
    workspace_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)]
):
    """获取工作空间成员列表"""
    # 验证workspace属于用户的租户
    workspace = await workspace_service.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    
    tenant_id = current_user.get("tenant_id")
    if workspace.get("tenant_id") != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您无权查看该工作空间的成员（跨租户访问被拒绝）"
        )
    
    # 验证用户是否是工作空间成员
    user_id = UUID(current_user["sub"])
    is_member = await workspace_service.is_workspace_member(workspace_id, user_id)
    
    if not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您无权查看该工作空间的成员（不是成员）"
        )
    
    result = await workspace_service.list_members(workspace_id)
    items = [WorkspaceMemberInfo(**item) for item in result]
    return WorkspaceMemberListResponse(success=True, data=items)


@router.delete("/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberRemoveResponse)
async def remove_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """移除工作空间成员"""
    # 验证workspace属于用户的租户
    workspace = await workspace_service.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    
    tenant_id = current_user.get("tenant_id")
    if workspace.get("tenant_id") != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您无权管理该工作空间的成员（跨租户访问被拒绝）"
        )
    
    # 验证用户是否有管理成员权限
    current_user_id = UUID(current_user["sub"])
    has_permission = await auth_service.verify_permission(
        user_id=current_user_id,
        resource_type="workspace",
        resource_id=workspace_id,
        action="manage_members"
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您无权管理该工作空间的成员（权限不足）"
        )
    
    success = await workspace_service.remove_member(workspace_id, user_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return WorkspaceMemberRemoveResponse(success=True, message="Member removed successfully")


@router.put("/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberAddResponse)
async def update_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    request: WorkspaceMemberUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_active_user)],
    workspace_service: Annotated[WorkspaceService, Depends(get_workspace_service)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """更新工作空间成员角色"""
    try:
        # 验证workspace属于用户的租户
        workspace = await workspace_service.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        
        tenant_id = current_user.get("tenant_id")
        if workspace.get("tenant_id") != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您无权管理该工作空间的成员（跨租户访问被拒绝）"
            )
        
        # 验证用户是否有管理成员权限
        current_user_id = UUID(current_user["sub"])
        has_permission = await auth_service.verify_permission(
            user_id=current_user_id,
            resource_type="workspace",
            resource_id=workspace_id,
            action="manage_members"
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您无权管理该工作空间的成员（权限不足）"
            )
        
        result = await workspace_service.update_member_role(
            workspace_id=workspace_id,
            user_id=user_id,
            role=request.role.value
        )
        return WorkspaceMemberAddResponse(
            success=True,
            message="Member role updated successfully",
            data=WorkspaceMemberInfo(**result)
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to update workspace member role: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update member role")