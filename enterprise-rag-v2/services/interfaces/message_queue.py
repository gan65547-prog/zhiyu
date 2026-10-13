"""
消息队列抽象接口

定义异步任务处理的消息队列接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable
from uuid import UUID
from datetime import datetime, timezone
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"


class TaskResult:
    """任务结果"""

    def __init__(
        self,
        task_id: str,
        status: TaskStatus,
        result: Any = None,
        error: Optional[str] = None,
        created_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ):
        self.task_id = task_id
        self.status = status
        self.result = result
        self.error = error
        self.created_at = created_at or datetime.now(timezone.utc)
        self.started_at = started_at
        self.completed_at = completed_at


class Message(ABC):
    """消息基类"""

    def __init__(
        self,
        topic: str,
        payload: Dict[str, Any],
        message_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        self.topic = topic
        self.payload = payload
        self.message_id = message_id or str(UUID())
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.headers = headers or {}


class MessageHandler(ABC):
    """消息处理器抽象接口"""

    @abstractmethod
    async def handle(self, message: Message) -> bool:
        """处理消息"""
        pass


class MessageQueue(ABC):
    """消息队列抽象接口"""

    @abstractmethod
    async def publish(self, topic: str, message: Message) -> bool:
        """
        发布消息到主题

        Args:
            topic: 主题名称
            message: 消息对象

        Returns:
            是否发布成功
        """
        pass

    @abstractmethod
    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """
        订阅主题

        Args:
            topic: 主题名称
            handler: 消息处理器
        """
        pass

    @abstractmethod
    async def unsubscribe(self, topic: str) -> None:
        """
        取消订阅

        Args:
            topic: 主题名称
        """
        pass


class TaskQueue(ABC):
    """任务队列抽象接口"""

    @abstractmethod
    async def create_task(
        self,
        task_name: str,
        payload: Dict[str, Any],
        delay: int = 0,
        retry_count: int = 0,
        retry_delay: int = 60
    ) -> str:
        """
        创建异步任务

        Args:
            task_name: 任务名称
            payload: 任务参数
            delay: 延迟执行秒数
            retry_count: 重试次数
            retry_delay: 重试延迟秒数

        Returns:
            任务ID
        """
        pass

    @abstractmethod
    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """
        获取任务结果

        Args:
            task_id: 任务ID

        Returns:
            任务结果
        """
        pass

    @abstractmethod
    async def revoke_task(self, task_id: str, terminate: bool = False) -> bool:
        """
        撤销任务

        Args:
            task_id: 任务ID
            terminate: 是否强制终止

        Returns:
            是否撤销成功
        """
        pass

    @abstractmethod
    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 100
    ) -> list:
        """
        列出任务

        Args:
            status: 任务状态过滤
            limit: 返回数量限制

        Returns:
            任务列表
        """
        pass
