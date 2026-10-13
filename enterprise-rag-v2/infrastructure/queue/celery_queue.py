"""
Celery任务队列实现

提供基于Celery的异步任务处理功能
"""

from typing import Any, Dict, Optional, Callable, List
from uuid import UUID
from datetime import datetime, timezone
import asyncio

from celery import Celery
from celery.result import AsyncResult
from redis.exceptions import RedisError

from infrastructure.logging.logger import get_logger

from services.interfaces.message_queue import (
    TaskQueue,
    MessageQueue,
    Message,
    MessageHandler,
    TaskResult,
    TaskStatus
)

logger = get_logger(__name__)


class CeleryTaskQueue(TaskQueue):
    """Celery任务队列实现"""

    def __init__(
        self,
        broker_url: str = "redis://localhost:6379/0",
        result_backend: str = "redis://localhost:6379/0",
        task_serializer: str = "json",
        result_serializer: str = "json",
        accept_content: List[str] = None
    ):
        self.celery = Celery(
            "tasks",
            broker=broker_url,
            backend=result_backend
        )

        self.celery.conf.update(
            task_serializer=task_serializer,
            result_serializer=result_serializer,
            accept_content=accept_content or ["json"],
            result_expires=3600,
            task_track_started=True,
            task_acks_late=True,
            task_reject_on_worker_lost=True
        )

        self._tasks: Dict[str, Callable] = {}
        self._task_results: Dict[str, TaskResult] = {}

    def register_task(self, name: str, func: Callable):
        """注册任务"""
        self._tasks[name] = func
        self.celery.task(name=name)(func)

    async def create_task(
        self,
        task_name: str,
        payload: Dict[str, Any],
        delay: int = 0,
        retry_count: int = 0,
        retry_delay: int = 60
    ) -> str:
        """创建异步任务"""
        if task_name not in self._tasks:
            raise ValueError(f"Task {task_name} not registered")

        task = self.celery.tasks.get(task_name)
        if not task:
            raise ValueError(f"Task {task_name} not found")

        task_id = str(UUID())

        async_result = task.apply_async(
            args=[payload],
            countdown=delay,
            retry=retry_count > 0,
            retry_policy={
                "max_retries": retry_count,
                "interval_start": retry_delay
            }
        )

        self._task_results[task_id] = TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
            result={"celery_task_id": async_result.id}
        )

        return task_id

    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """获取任务结果"""
        if task_id in self._task_results:
            cached_result = self._task_results[task_id]

            if cached_result.status in [TaskStatus.SUCCESS, TaskStatus.FAILURE]:
                return cached_result

            celery_task_id = cached_result.result.get("celery_task_id")
            if celery_task_id:
                async_result = AsyncResult(celery_task_id, app=self.celery)

                if async_result.ready():
                    if async_result.successful():
                        cached_result.status = TaskStatus.SUCCESS
                        cached_result.result = async_result.result
                        cached_result.completed_at = datetime.now(timezone.utc)
                    elif async_result.failed():
                        cached_result.status = TaskStatus.FAILURE
                        cached_result.error = str(async_result.result)
                        cached_result.completed_at = datetime.now(timezone.utc)

            return cached_result

        return None

    async def revoke_task(self, task_id: str, terminate: bool = False) -> bool:
        """撤销任务"""
        if task_id not in self._task_results:
            return False

        cached_result = self._task_results[task_id]
        celery_task_id = cached_result.result.get("celery_task_id")

        if celery_task_id:
            self.celery.control.revoke(celery_task_id, terminate=terminate)

        cached_result.status = TaskStatus.FAILURE
        cached_result.error = "Task revoked"
        cached_result.completed_at = datetime.now(timezone.utc)

        return True

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 100
    ) -> list:
        """列出任务"""
        tasks = list(self._task_results.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        return tasks[:limit]


class RedisMessageQueue(MessageQueue):
    """Redis消息队列实现"""

    def __init__(self, url: str = "redis://localhost:6379/0"):
        import redis.asyncio as redis
        self.redis_url = url
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._handlers: Dict[str, MessageHandler] = {}
        self._listener_task: Optional[asyncio.Task] = None

    async def _get_client(self):
        """获取Redis客户端"""
        if self._client is None:
            import redis.asyncio as redis
            self._client = redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    async def publish(self, topic: str, message: Message) -> bool:
        """发布消息"""
        import json

        client = await self._get_client()

        try:
            payload = {
                "message_id": message.message_id,
                "topic": message.topic,
                "payload": message.payload,
                "timestamp": message.timestamp.isoformat(),
                "headers": message.headers
            }

            await client.publish(topic, json.dumps(payload))
            return True
        except (RedisError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            logger.warning("发布 Redis 消息失败: topic=%s error=%s", topic, exc, exc_info=True)
            return False

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """订阅主题"""
        self._handlers[topic] = handler

    async def unsubscribe(self, topic: str) -> None:
        """取消订阅"""
        if topic in self._handlers:
            del self._handlers[topic]

    async def start_listening(self) -> None:
        """开始监听消息"""
        if self._listener_task is not None:
            return

        async def listen():
            client = await self._get_client()
            pubsub = client.pubsub()

            for topic in self._handlers.keys():
                await pubsub.subscribe(topic)

            async for message in pubsub.listen():
                if message["type"] == "message":
                    topic = message["channel"]
                    if topic in self._handlers:
                        import json
                        data = json.loads(message["data"])
                        msg = Message(
                            topic=data["topic"],
                            payload=data["payload"],
                            message_id=data["message_id"],
                            headers=data.get("headers", {})
                        )
                        await self._handlers[topic].handle(msg)

        self._listener_task = asyncio.create_task(listen())

    async def stop_listening(self) -> None:
        """停止监听"""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
