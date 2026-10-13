"""
备份路由

处理备份管理相关的API端点
"""

from typing import Annotated, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from api.deps import get_db, get_current_active_user
from services.backup.service import BackupServiceImpl
from infrastructure.logging.logger import get_logger


router = APIRouter()
logger = get_logger(__name__)


class BackupCreateRequest(BaseModel):
    backup_type: str = "full"
    base_backup_id: Optional[str] = None


class BackupRestoreRequest(BaseModel):
    target_tenant_id: str


class BackupScheduleRequest(BaseModel):
    schedule_type: str = "full"
    interval_hours: int = 24


@router.post("/create")
async def create_backup(
    request: BackupCreateRequest,
    tenant_id: str = Query(...),
    db: Annotated = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """创建备份"""
    backup_service = BackupServiceImpl(db)

    try:
        if request.backup_type == "full":
            result = await backup_service.create_full_backup(UUID(tenant_id))
        elif request.backup_type == "incremental":
            if not request.base_backup_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="base_backup_id is required for incremental backup"
                )
            result = await backup_service.create_incremental_backup(
                UUID(tenant_id),
                request.base_backup_id
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid backup type"
            )

        return {
            "success": True,
            "data": {
                "backup_id": result.id,
                "status": result.status,
                "backup_type": result.backup_type,
                "created_at": result.created_at.isoformat() if result.created_at else None
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to create backup: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create backup")


@router.post("/{backup_id}/restore")
async def restore_backup(
    backup_id: str,
    request: BackupRestoreRequest,
    db: Annotated = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """从备份恢复"""
    backup_service = BackupServiceImpl(db)

    try:
        result = await backup_service.restore_from_backup(
            backup_id,
            UUID(request.target_tenant_id)
        )

        return {
            "success": True,
            "data": {
                "restore_id": result.id,
                "status": result.status,
                "backup_id": result.backup_id,
                "created_at": result.created_at.isoformat() if result.created_at else None
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except (RuntimeError, TypeError, AttributeError) as e:
        logger.exception("Failed to restore backup %s: %s", backup_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to restore backup")


@router.get("/list")
async def list_backups(
    tenant_id: Optional[str] = Query(None),
    backup_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Annotated = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """列出备份"""
    backup_service = BackupServiceImpl(db)

    try:
        backups = await backup_service.list_backups(
            tenant_id=UUID(tenant_id) if tenant_id else None,
            backup_type=backup_type,
            status=status_filter
        )

        return {
            "success": True,
            "data": [
                {
                    "backup_id": b.id,
                    "backup_type": b.backup_type,
                    "status": b.status,
                    "size_bytes": b.size_bytes,
                    "file_path": b.file_path,
                    "created_at": b.created_at.isoformat() if b.created_at else None,
                    "completed_at": b.completed_at.isoformat() if b.completed_at else None,
                    "error_message": b.error_message
                }
                for b in backups
            ]
        }
    except (RuntimeError, ValueError, TypeError, AttributeError) as e:
        logger.exception("Failed to list backups: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list backups")


@router.get("/{backup_id}")
async def get_backup_status(
    backup_id: str,
    db: Annotated = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """获取备份状态"""
    backup_service = BackupServiceImpl(db)

    result = await backup_service.get_backup_status(backup_id)

    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found")

    return {
        "success": True,
        "data": {
            "backup_id": result.id,
            "backup_type": result.backup_type,
            "status": result.status,
            "size_bytes": result.size_bytes,
            "file_path": result.file_path,
            "created_at": result.created_at.isoformat() if result.created_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "error_message": result.error_message
        }
    }


@router.delete("/{backup_id}")
async def delete_backup(
    backup_id: str,
    db: Annotated = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """删除备份"""
    backup_service = BackupServiceImpl(db)

    success = await backup_service.delete_backup(backup_id)

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found")

    return {
        "success": True,
        "message": "Backup deleted successfully"
    }


@router.post("/schedule")
async def schedule_backup(
    request: BackupScheduleRequest,
    tenant_id: str = Query(...),
    db: Annotated = Depends(get_db),
    current_user: dict = Depends(get_current_active_user)
):
    """设置备份计划"""
    backup_service = BackupServiceImpl(db)

    try:
        schedule_id = await backup_service.schedule_backup(
            UUID(tenant_id),
            request.schedule_type,
            request.interval_hours
        )

        return {
            "success": True,
            "data": {
                "schedule_id": schedule_id,
                "schedule_type": request.schedule_type,
                "interval_hours": request.interval_hours
            }
        }
    except (RuntimeError, ValueError, TypeError, AttributeError) as e:
        logger.exception("Failed to schedule backup: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to schedule backup")
