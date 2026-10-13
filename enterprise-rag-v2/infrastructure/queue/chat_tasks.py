"""
聊天异步任务定义（提交任务 + 状态轮询）。
"""

from typing import Any, Dict, Optional
from uuid import UUID

from infrastructure.database.session import AsyncSessionLocal
from infrastructure.logging.logger import get_logger
from infrastructure.queue.celery_app import celery_app
from infrastructure.queue.celery_asyncio import get_worker_event_loop, run_coroutine
from services.impl.chat_service import ChatServiceImpl

logger = get_logger("infrastructure.queue.chat_tasks")


async def _process_chat_async(payload: Dict[str, Any]) -> Dict[str, Any]:
    dataset_id = UUID(str(payload["dataset_id"]))
    user_id = str(payload["user_id"])
    tenant_id = str(payload["tenant_id"])
    conversation_id_raw: Optional[str] = payload.get("conversation_id")
    conversation_id = UUID(conversation_id_raw) if conversation_id_raw else None

    async with AsyncSessionLocal() as session:
        chat_service = ChatServiceImpl(session)
        await chat_service.verify_dataset_access(dataset_id, user_id, tenant_id)

        final_conversation_id = conversation_id_raw
        async for chunk in chat_service.chat_stream(
            dataset_id=dataset_id,
            query=str(payload["query"]),
            conversation_id=conversation_id,
            history=payload.get("history") or None,
            retrieval_mode=str(payload.get("retrieval_mode") or "hybrid"),
            top_k=int(payload.get("top_k") or 5),
            temperature=float(payload.get("temperature") or 0.7),
            max_tokens=int(payload.get("max_tokens") or 2000),
            user_id=user_id,
            tenant_id=tenant_id,
        ):
            cid = chunk.get("conversation_id")
            if cid:
                final_conversation_id = str(cid)

        # Celery 任务没有 FastAPI 请求上下文，不会自动提交事务，这里需显式 commit。
        await session.commit()

        return {
            "success": True,
            "conversation_id": final_conversation_id,
        }


@celery_app.task(name="chat.process_async", bind=True)
def process_chat_async_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Celery worker 执行聊天任务。"""
    loop = get_worker_event_loop()
    task_id = getattr(self.request, "id", None)
    try:
        logger.info(
            "[Celery/chat] 开始 task_id=%s loop_id=%s dataset_id=%s user_id=%s tenant_id=%s "
            "conversation_id=%s retrieval_mode=%s",
            task_id,
            id(loop),
            payload.get("dataset_id"),
            payload.get("user_id"),
            payload.get("tenant_id"),
            payload.get("conversation_id"),
            payload.get("retrieval_mode") or "hybrid",
        )
        result = run_coroutine(_process_chat_async(payload))
        logger.info(
            "[Celery/chat] 完成 task_id=%s loop_id=%s conversation_id=%s",
            task_id,
            id(loop),
            result.get("conversation_id"),
        )
        return result
    except (ValueError, RuntimeError, TypeError, AttributeError) as e:
        logger.error(
            "[Celery/chat] 失败 task_id=%s loop_id=%s dataset_id=%s user_id=%s error=%s",
            task_id,
            id(loop),
            payload.get("dataset_id"),
            payload.get("user_id"),
            e,
            exc_info=True,
        )
        raise
