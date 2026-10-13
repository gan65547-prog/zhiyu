"""
Celery任务定义

提供文档处理等异步任务
"""

from typing import Dict, Any
from uuid import UUID

from infrastructure.queue.celery_queue import CeleryTaskQueue
from services.interfaces.document_service import DocumentService
from infrastructure.database.session import AsyncSessionLocal
from services.impl.document_service import DocumentServiceImpl
from infrastructure.logging.logger import get_logger

logger = get_logger("infrastructure.queue.tasks")

# 全局任务队列实例
task_queue = None

def get_task_queue() -> CeleryTaskQueue:
    """获取任务队列实例"""
    global task_queue
    if task_queue is None:
        from core.config import get_settings
        settings = get_settings()
        task_queue = CeleryTaskQueue(
            broker_url=settings.celery.broker_url,
            result_backend=settings.celery.result_backend,
            task_serializer=settings.celery.task_serializer,
            result_serializer=settings.celery.result_serializer
        )
        # 注册任务
        task_queue.register_task("process_document", process_document_task)
    return task_queue


async def process_document_task(payload: Dict[str, Any]):
    """
    处理文档的异步任务
    
    Args:
        payload: 任务参数，包含 document_id
    """
    document_id = payload.get("document_id")
    if not document_id:
        logger.error("Missing document_id in task payload")
        return {"success": False, "error": "Missing document_id"}
    
    try:
        logger.info(f"开始处理文档 (异步), document_id={document_id}")
        
        # 创建数据库会话
        async with AsyncSessionLocal() as session:
            # 创建文档服务实例
            document_service = DocumentServiceImpl(session)
            
            # 处理文档
            success = await document_service.process_document(UUID(document_id))
            
            if success:
                logger.info(f"文档处理成功 (异步), document_id={document_id}")
                return {"success": True, "document_id": document_id}
            else:
                logger.error(f"文档处理失败 (异步), document_id={document_id}")
                return {"success": False, "error": "Document processing failed"}
    except (ValueError, RuntimeError, TypeError, AttributeError) as e:
        logger.error(f"处理文档任务失败: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
