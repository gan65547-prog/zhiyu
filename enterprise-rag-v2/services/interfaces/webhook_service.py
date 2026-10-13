"""
Webhook服务接口定义

定义接收第三方平台Webhook的接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timezone


class WebhookEvent:
    """Webhook事件"""

    def __init__(
        self,
        event_id: str,
        event_type: str,
        provider: str,
        payload: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        self.event_id = event_id
        self.event_type = event_type
        self.provider = provider
        self.payload = payload
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.headers = headers or {}


class WebhookHandler(ABC):
    """Webhook处理器抽象接口"""

    @abstractmethod
    async def handle(self, event: WebhookEvent) -> Dict[str, Any]:
        """
        处理Webhook事件

        Args:
            event: Webhook事件

        Returns:
            处理结果
        """
        pass

    @abstractmethod
    def supports(self, event_type: str) -> bool:
        """
        检查是否支持该事件类型

        Args:
            event_type: 事件类型

        Returns:
            是否支持
        """
        pass


class WebhookServiceInterface(ABC):
    """Webhook服务接口"""

    @abstractmethod
    async def register_handler(
        self,
        provider: str,
        event_type: str,
        handler: WebhookHandler
    ) -> None:
        """
        注册Webhook处理器

        Args:
            provider: 提供商
            event_type: 事件类型
            handler: 处理器
        """
        pass

    @abstractmethod
    async def handle_webhook(
        self,
        provider: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        处理Webhook请求

        Args:
            provider: 提供商
            payload: 请求载荷
            headers: 请求头

        Returns:
            处理结果
        """
        pass

    @abstractmethod
    async def verify_webhook_signature(
        self,
        provider: str,
        signature: str,
        payload: bytes
    ) -> bool:
        """
        验证Webhook签名

        Args:
            provider: 提供商
            signature: 签名
            payload: 请求体

        Returns:
            是否验证通过
        """
        pass

    @abstractmethod
    async def send_webhook(
        self,
        provider: str,
        event_type: str,
        payload: Dict[str, Any]
    ) -> bool:
        """
        发送Webhook（用于回调通知）

        Args:
            provider: 提供商
            event_type: 事件类型
            payload: 载荷

        Returns:
            是否发送成功
        """
        pass
