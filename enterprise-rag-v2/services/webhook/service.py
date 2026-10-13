"""
Webhook服务实现

提供Webhook事件处理和路由功能
"""

from typing import Dict, Any, Optional, Callable
from uuid import UUID, uuid4
from datetime import datetime
import hashlib
import hmac
import json

from services.interfaces.webhook_service import (
    WebhookServiceInterface,
    WebhookEvent,
    WebhookHandler
)


class WebhookServiceImpl(WebhookServiceInterface):
    """Webhook服务实现"""

    def __init__(self):
        self._handlers: Dict[str, Dict[str, WebhookHandler]] = {}
        self._signature_verifiers: Dict[str, Callable] = {}

    async def register_handler(
        self,
        provider: str,
        event_type: str,
        handler: WebhookHandler
    ) -> None:
        """注册Webhook处理器"""
        if provider not in self._handlers:
            self._handlers[provider] = {}
        self._handlers[provider][event_type] = handler

    async def handle_webhook(
        self,
        provider: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """处理Webhook请求"""
        if provider not in self._handlers:
            return {"status": "ignored", "message": f"No handlers for provider: {provider}"}

        event_type = self._extract_event_type(provider, payload)

        if event_type not in self._handlers[provider]:
            return {"status": "ignored", "message": f"No handler for event type: {event_type}"}

        event = WebhookEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            provider=provider,
            payload=payload,
            headers=headers or {}
        )

        handler = self._handlers[provider][event_type]

        try:
            result = await handler.handle(event)
            return {"status": "success", "result": result}
        except (RuntimeError, ValueError, TypeError, KeyError, AttributeError) as e:
            return {"status": "error", "message": str(e)}

    async def verify_webhook_signature(
        self,
        provider: str,
        signature: str,
        payload: bytes
    ) -> bool:
        """验证Webhook签名"""
        if provider not in self._signature_verifiers:
            return True

        verifier = self._signature_verifiers[provider]
        return verifier(signature, payload)

    async def send_webhook(
        self,
        provider: str,
        event_type: str,
        payload: Dict[str, Any]
    ) -> bool:
        """发送Webhook"""
        return True

    def register_signature_verifier(self, provider: str, verifier: Callable) -> None:
        """注册签名验证器"""
        self._signature_verifiers[provider] = verifier

    def _extract_event_type(self, provider: str, payload: Dict[str, Any]) -> str:
        """提取事件类型"""
        if provider == "feishu":
            # v2 格式优先: header.event_type
            v2_type = payload.get("header", {}).get("event_type")
            if v2_type:
                return v2_type
            # 旧格式: event.type
            return payload.get("event", {}).get("type", "unknown")
        elif provider == "wechat_work":
            return payload.get("msg_type", "unknown")
        else:
            return payload.get("event_type", "unknown")


class FeishuWebhookHandler(WebhookHandler):
    """飞书Webhook处理器"""

    async def handle(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理飞书Webhook事件"""
        event_type = event.event_type

        handlers = {
            "im.message.receive_v1": self._handle_message,
            "im.message.read_v1": self._handle_read,
            "contact.user.created_v3": self._handle_user_created,
            "contact.user.deleted_v3": self._handle_user_deleted,
        }

        handler = handlers.get(event_type)
        if handler:
            return await handler(event)
        return {"status": "handled", "event_type": event_type}

    def supports(self, event_type: str) -> bool:
        """检查是否支持该事件类型"""
        return event_type in [
            "im.message.receive_v1",
            "im.message.read_v1",
            "contact.user.created_v3",
            "contact.user.deleted_v3"
        ]

    async def _handle_message(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理接收消息"""
        message = event.payload.get("event", {})
        sender = message.get("sender", {})
        content = message.get("content", {})

        return {
            "status": "processed",
            "message_id": message.get("message_id"),
            "sender_id": sender.get("sender_id", {}).get("open_id"),
            "content": content
        }

    async def _handle_read(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理消息已读"""
        return {"status": "processed"}

    async def _handle_user_created(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理用户创建"""
        return {"status": "processed"}

    async def _handle_user_deleted(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理用户删除"""
        return {"status": "processed"}


class WeChatWorkWebhookHandler(WebhookHandler):
    """企业微信Webhook处理器"""

    async def handle(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理企业微信Webhook事件"""
        msg_type = event.event_type

        handlers = {
            "text": self._handle_text_message,
            "image": self._handle_image_message,
            "voice": self._handle_voice_message,
            "event": self._handle_event_message,
        }

        handler = handlers.get(msg_type)
        if handler:
            return await handler(event)
        return {"status": "handled", "msg_type": msg_type}

    def supports(self, event_type: str) -> bool:
        """检查是否支持该事件类型"""
        return event_type in ["text", "image", "voice", "event"]

    async def _handle_text_message(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理文本消息"""
        content = event.payload.get("Content", "")

        return {
            "status": "processed",
            "from_user": event.payload.get("FromUserName"),
            "content": content
        }

    async def _handle_image_message(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理图片消息"""
        return {
            "status": "processed",
            "from_user": event.payload.get("FromUserName"),
            "media_id": event.payload.get("MediaId")
        }

    async def _handle_voice_message(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理语音消息"""
        return {
            "status": "processed",
            "from_user": event.payload.get("FromUserName"),
            "media_id": event.payload.get("MediaId")
        }

    async def _handle_event_message(self, event: WebhookEvent) -> Dict[str, Any]:
        """处理事件消息"""
        event_type = event.payload.get("Event", "")

        return {
            "status": "processed",
            "event": event_type,
            "from_user": event.payload.get("FromUserName")
        }


class WebhookSignatureVerifier:
    """Webhook签名验证工具"""

    @staticmethod
    def verify_feishu(signature: str, payload: bytes, secret: str) -> bool:
        """验证飞书签名"""
        if not signature:
            return False

        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    @staticmethod
    def verify_wechat_work(signature: str, token: str, timestamp: str, nonce: str, payload: bytes) -> bool:
        """验证企业微信签名"""
        if not signature:
            return False

        data = "".join(sorted([token, timestamp, nonce]))
        expected = hashlib.sha1(data.encode()).hexdigest()

        return hmac.compare_digest(signature, expected)
