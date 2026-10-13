"""
数据集路由

处理数据集管理相关的API端点
"""

from typing import Annotated, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from api.schemas.base import BaseResponse, DataResponse, PaginatedResponse
from api.schemas.dataset import DatasetCreate, DatasetUpdate, DatasetQuery, DatasetResponse
from api.deps import get_dataset_service, get_current_active_user, get_auth_service
from services.interfaces.dataset_service import DatasetService
from services.interfaces.auth_service import AuthService
from core.value_objects.pagination import Pagination
from infrastructure.logging.logger import get_logger


router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=DataResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    request: DatasetCreate,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """创建数据集"""
    try:
        user_id = current_user["sub"]
        tenant_id = current_user.get("tenant_id")
        tenant_key = str(tenant_id) if tenant_id else None
        
        # 如果没有提供workspace_id，获取用户的默认工作空间
        workspace_id = request.workspace_id
        if not workspace_id:
            from infrastructure.database.models import Workspace, WorkspaceMember
            from sqlalchemy import select
            
            # 获取用户的第一个工作空间
            result = await dataset_service.session.execute(
                select(Workspace)
                .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
                .where(
                    WorkspaceMember.user_id == user_id,
                    Workspace.tenant_id == tenant_key  # 确保只获取当前租户的workspace
                )
                .limit(1)
            )
            workspace = result.scalar_one_or_none()
            
            if not workspace:
                raise ValueError("用户没有工作空间，请先创建工作空间")
            
            workspace_id = workspace.id
        
        # 验证用户是否有在该工作空间创建数据集的权限
        # 检查workspace_id的类型，如果是字符串则转换为UUID
        if isinstance(workspace_id, str):
            workspace_id_uuid = UUID(workspace_id)
        else:
            workspace_id_uuid = workspace_id
        
        has_permission = await auth_service.verify_permission(
            user_id=UUID(user_id),
            resource_type="workspace",
            resource_id=workspace_id_uuid,
            action="edit"
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您无权在该工作空间创建数据集（权限不足）"
            )
        
        result = await dataset_service.create_dataset(
            workspace_id=workspace_id,
            name=request.name,
            description=request.description,
            embedding_model=request.embedding_model,
            chunk_size=request.chunk_size or 500,
            chunk_overlap=request.chunk_overlap or 50,
            metadata=request.metadata,
            user_id=user_id,
            tenant_id=tenant_id
        )
        return DataResponse(success=True, message="Dataset created successfully", data=result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to create dataset: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create dataset")


@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: UUID,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)]
):
    """获取数据集详情"""
    try:
        user_id = current_user["sub"]
        tenant_id = current_user.get("tenant_id")

        # 验证dataset和workspace权限
        await dataset_service.verify_dataset_access(
            dataset_id=dataset_id,
            user_id=user_id,
            tenant_id=tenant_id
        )

        result = await dataset_service.get_dataset(dataset_id)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.put("/{dataset_id}")
async def update_dataset(
    dataset_id: UUID,
    request: DatasetUpdate,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """更新数据集"""
    try:
        user_id = current_user["sub"]
        tenant_id = current_user.get("tenant_id")
        
        # 验证dataset和workspace权限（写操作）
        await dataset_service.verify_dataset_access(
            dataset_id=dataset_id,
            user_id=user_id,
            tenant_id=tenant_id,
            action="write",
        )

        # 验证用户是否有编辑权限
        has_permission = await auth_service.verify_permission(
            user_id=UUID(user_id),
            resource_type="dataset",
            resource_id=dataset_id,
            action="edit"
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您无权编辑该数据集（权限不足）"
            )

        update_data = request.model_dump(exclude_unset=True)
        result = await dataset_service.update_dataset(dataset_id, **update_data)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to update dataset: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update dataset")


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: UUID,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """删除数据集"""
    user_id = current_user["sub"]
    tenant_id = current_user.get("tenant_id")
    
    # 验证dataset和workspace权限（写操作）
    await dataset_service.verify_dataset_access(
        dataset_id=dataset_id,
        user_id=user_id,
        tenant_id=tenant_id,
        action="write",
    )

    # 验证用户是否有删除权限
    has_permission = await auth_service.verify_permission(
        user_id=UUID(user_id),
        resource_type="dataset",
        resource_id=dataset_id,
        action="delete"
    )
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您无权删除该数据集（权限不足）"
        )
    
    success = await dataset_service.delete_dataset(dataset_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return {"success": True, "message": "Dataset deleted successfully"}


@router.get("/")
async def list_datasets(
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    workspace_id: Optional[str] = Query(None),
    include_public: bool = Query(False),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000)
):
    """查询数据集列表"""
    user_id = current_user["sub"]
    tenant_id = current_user.get("tenant_id")
    
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户缺少租户信息")
    tenant_key = str(tenant_id)

    # 如果没有提供workspace_id，获取用户的默认工作空间
    if not workspace_id:
        from infrastructure.database.models import Workspace, WorkspaceMember
        from sqlalchemy import select
        
        # 获取用户的第一个工作空间（确保只获取当前租户的）
        result = await dataset_service.session.execute(
            select(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                WorkspaceMember.user_id == user_id,
                Workspace.tenant_id == tenant_key  # 租户隔离
            )
            .limit(1)
        )
        workspace = result.scalar_one_or_none()
        
        if not workspace:
            # 如果用户没有工作空间，返回空列表
            return {
                "success": True,
                "data": {
                    "items": [],
                    "total": 0,
                    "page": page,
                    "page_size": page_size
                }
            }
        
        workspace_id = workspace.id
    else:
        # 如果提供了workspace_id，验证用户有权访问该workspace
        from infrastructure.database.models import Workspace, WorkspaceMember
        from sqlalchemy import select
        
        workspace_result = await dataset_service.session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        workspace = workspace_result.scalar_one_or_none()
        
        if not workspace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        
        # 验证租户隔离
        if str(workspace.tenant_id) != tenant_key:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您无权访问该工作空间")

        # 公共工作空间：同租户内所有用户自动可读，跳过成员检查
        workspace_meta = workspace.extra_metadata or {}
        if workspace_meta.get("is_public_workspace") is not True:
            # 验证用户是workspace成员
            member_result = await dataset_service.session.execute(
                select(WorkspaceMember)
                .where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == user_id
                )
            )
            member = member_result.scalar_one_or_none()

            if not member:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="您不是该工作空间的成员")
    
    pagination = Pagination(page=page, page_size=page_size)
    result = await dataset_service.list_datasets(
        workspace_id=workspace_id,
        keyword=keyword,
        pagination=pagination,
        include_public=include_public,
        tenant_id=tenant_key,
    )

    return {
        "success": True,
        "data": {
            "items": result.items,
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size
        }
    }


@router.get("/{dataset_id}/statistics")
async def get_dataset_statistics(
    dataset_id: UUID,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)]
):
    """获取数据集统计信息"""
    try:
        user_id = current_user["sub"]
        tenant_id = current_user.get("tenant_id")
        
        # 验证dataset和workspace权限
        await dataset_service.verify_dataset_access(
            dataset_id=dataset_id,
            user_id=user_id,
            tenant_id=tenant_id
        )
        
        result = await dataset_service.get_dataset_statistics(dataset_id)
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to get dataset statistics: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get dataset statistics")


@router.get("/{dataset_id}/copy_status")
async def get_dataset_copy_status(
    dataset_id: UUID,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)]
):
    """获取数据集文档复制状态

    返回数据集的文档复制状态信息，包括已复制文档数量和复制任务状态。
    """
    try:
        user_id = current_user["sub"]
        tenant_id = current_user.get("tenant_id")

        # 验证dataset和workspace权限
        await dataset_service.verify_dataset_access(
            dataset_id=dataset_id,
            user_id=user_id,
            tenant_id=tenant_id
        )

        # 获取数据集详情
        dataset = await dataset_service.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        # 获取数据集下的文档数量
        from sqlalchemy import select, func
        from infrastructure.database.models import Document, DocumentCopyStatus
        from infrastructure.database.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count()).select_from(Document).where(Document.dataset_id == str(dataset_id))
            )
            document_count = result.scalar() or 0
            
            # 查询文档复制状态
            copy_status_result = await session.execute(
                select(DocumentCopyStatus).where(
                    DocumentCopyStatus.dataset_id == str(dataset_id)
                ).order_by(DocumentCopyStatus.created_at.desc())
            )
            copy_status = copy_status_result.scalar_one_or_none()

        if copy_status:
            # 如果有历史记录，使用记录中的状态
            return {
                "success": True,
                "data": {
                    "dataset_id": str(dataset_id),
                    "dataset_name": dataset.get("name"),
                    "copy_status": copy_status.status,
                    "total_documents": copy_status.total_documents,
                    "completed_documents": copy_status.completed_documents,
                    "failed_documents": copy_status.failed_documents,
                    "task_id": copy_status.task_id,
                    "error_message": copy_status.error_message,
                    "document_count": document_count,
                    "created_at": copy_status.created_at.isoformat() if copy_status.created_at else None,
                    "updated_at": copy_status.updated_at.isoformat() if copy_status.updated_at else None
                }
            }
        else:
            # 如果没有历史记录，根据文档数量判断（向后兼容）
            copy_task_status = "completed" if document_count > 0 else "pending"
            return {
                "success": True,
                "data": {
                    "dataset_id": str(dataset_id),
                    "dataset_name": dataset.get("name"),
                    "copy_status": copy_task_status,
                    "document_count": document_count,
                    "message": "文档复制完成" if copy_task_status == "completed" else "待复制"
                }
            }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to get dataset copy status: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get dataset copy status")


@router.post("/{dataset_id}/retry_copy")
async def retry_dataset_copy(
    dataset_id: UUID,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    current_user: Annotated[dict, Depends(get_current_active_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)]
):
    """重试数据集文档复制

    重新触发文档复制任务，将系统模板文档复制到指定数据集。
    仅管理员可执行此操作。
    """
    try:
        user_id = current_user["sub"]
        tenant_id = current_user.get("tenant_id")

        # 验证dataset和workspace权限（写操作）
        await dataset_service.verify_dataset_access(
            dataset_id=dataset_id,
            user_id=user_id,
            tenant_id=tenant_id,
            action="write",
        )

        # 验证用户是否有管理权限
        has_permission = await auth_service.verify_permission(
            user_id=UUID(user_id),
            resource_type="dataset",
            resource_id=dataset_id,
            action="edit"
        )
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您无权管理该数据集"
            )

        # 获取数据集详情以获取workspace_id
        dataset = await dataset_service.get_dataset(dataset_id)
        if not dataset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

        # 获取工作空间信息
        workspace_id = dataset.get("workspace_id")

        # 触发异步复制任务
        try:
            from infrastructure.queue.document_tasks import copy_template_documents_task
            copy_template_documents_task.delay(
                str(workspace_id),
                str(dataset_id)
            )
            message = "文档复制任务已触发"
        except Exception as e:
            logger.warning(f"触发文档复制任务失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="触发文档复制任务失败"
            )

        return {
            "success": True,
            "message": message
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to retry dataset copy: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retry dataset copy")
