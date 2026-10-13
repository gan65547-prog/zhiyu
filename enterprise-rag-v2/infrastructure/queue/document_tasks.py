"""
文档异步任务定义
"""

from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import update

from infrastructure.database.session import AsyncSessionLocal
from infrastructure.database.models import DocumentCopyStatus
from infrastructure.logging.logger import get_logger
from infrastructure.queue.celery_app import celery_app
from infrastructure.queue.celery_asyncio import get_worker_event_loop, run_coroutine
from services.impl.document_service import DocumentServiceImpl

logger = get_logger("infrastructure.queue.document_tasks")


async def _process_document_async(document_id_str: str) -> bool:
    async with AsyncSessionLocal() as session:
        document_service = DocumentServiceImpl(session)
        return await document_service.process_document(document_id_str)


@celery_app.task(name="document.process")
def process_document_task(document_id_str: str) -> dict:
    """Celery worker 执行文档处理任务。"""
    loop = get_worker_event_loop()
    try:
        logger.info(
            "[Celery/document] 开始 document_id=%s loop_id=%s",
            document_id_str,
            id(loop),
        )
        success = run_coroutine(_process_document_async(document_id_str))
        if success:
            logger.info(
                "[Celery/document] 成功 document_id=%s loop_id=%s",
                document_id_str,
                id(loop),
            )
            return {"success": True, "document_id": document_id_str}
        logger.error(
            "[Celery/document] 处理返回失败 document_id=%s loop_id=%s",
            document_id_str,
            id(loop),
        )
        return {"success": False, "document_id": document_id_str}
    except (ValueError, RuntimeError, TypeError, AttributeError) as e:
        logger.error(
            "[Celery/document] 异常 document_id=%s loop_id=%s error=%s",
            document_id_str,
            id(loop),
            e,
            exc_info=True,
        )
        raise
    finally:
        import gc
        gc.collect()


async def _copy_template_documents_async_impl(target_workspace_id: str, target_dataset_id: str) -> dict:
    """从系统模板复制文档到目标知识库"""
    from services.impl.document_copy_service import DocumentCopyService

    async with AsyncSessionLocal() as session:
        copy_service = DocumentCopyService(session)
        copied_docs = await copy_service.copy_template_documents(
            target_workspace_id=UUID(target_workspace_id),
            target_dataset_id=UUID(target_dataset_id)
        )
        return {
            "success": True,
            "workspace_id": target_workspace_id,
            "dataset_id": target_dataset_id,
            "copied_count": len(copied_docs)
        }


@celery_app.task(
    name="document.copy_template",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
)
def copy_template_documents_task(self, target_workspace_id: str, target_dataset_id: str) -> dict:
    """Celery worker 执行模板文档复制任务。

    Args:
        target_workspace_id: 目标工作空间ID
        target_dataset_id: 目标数据集ID

    Returns:
        dict: 包含复制结果的字典
    """
    loop = get_worker_event_loop()
    
    # 记录任务开始状态
    async def update_status(status: str, error_message: str = None):
        async with AsyncSessionLocal() as session:
            try:
                await session.execute(
                    update(DocumentCopyStatus).where(
                        DocumentCopyStatus.dataset_id == target_dataset_id
                    ).values(
                        status=status,
                        error_message=error_message,
                        updated_at=datetime.now(timezone.utc)
                    )
                )
                await session.commit()
            except Exception as e:
                logger.error(f"更新复制状态失败: {e}")
    
    try:
        logger.info(
            "[Celery/copy_template] 开始 workspace_id=%s dataset_id=%s loop_id=%s",
            target_workspace_id,
            target_dataset_id,
            id(loop),
        )
        
        # 更新状态为处理中
        run_coroutine(update_status("processing"))
        
        result = run_coroutine(_copy_template_documents_async_impl(target_workspace_id, target_dataset_id))
        
        # 更新状态为完成
        run_coroutine(update_status("completed"))
        
        logger.info(
            "[Celery/copy_template] 成功 workspace_id=%s dataset_id=%s copied=%s",
            target_workspace_id,
            target_dataset_id,
            result.get("copied_count", 0),
        )
        return result
    except (ConnectionError, TimeoutError) as exc:
        logger.warning(
            "[Celery/copy_template] 连接错误，准备重试 workspace_id=%s dataset_id=%s error=%s",
            target_workspace_id,
            target_dataset_id,
            exc,
        )
        raise self.retry(exc=exc)
    except Exception as exc:
        logger.error(
            "[Celery/copy_template] 异常 workspace_id=%s dataset_id=%s error=%s",
            target_workspace_id,
            target_dataset_id,
            exc,
            exc_info=True,
        )
        
        # 记录失败状态
        run_coroutine(update_status("failed", str(exc)))

        # 这里可以添加告警通知逻辑
        # 例如：发送邮件给管理员或使用其他通知渠道
        # await notify_admin_async(f"文档复制失败: {exc}")
        
        raise
    finally:
        import gc
        gc.collect()
