"""
Webhook路由

处理第三方平台Webhook的API端点
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Request, Header, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any

from services.webhook.service import WebhookServiceImpl, FeishuWebhookHandler, WeChatWorkWebhookHandler
from services.interfaces.webhook_service import WebhookServiceInterface
from infrastructure.logging.logger import get_logger


router = APIRouter()
logger = get_logger(__name__)


class WebhookRequest(BaseModel):
    """Webhook请求"""
    event_type: str
    payload: Dict[str, Any]


class WebhookResponse(BaseModel):
    """Webhook响应"""
    status: str
    message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


_webhook_service: Optional[WebhookServiceImpl] = None


def get_webhook_service() -> WebhookServiceInterface:
    """获取Webhook服务"""
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookServiceImpl()
        _webhook_service.register_handler("feishu", "im.message.receive_v1", FeishuWebhookHandler())
        _webhook_service.register_handler("feishu", "im.message.read_v1", FeishuWebhookHandler())
        _webhook_service.register_handler("feishu", "contact.user.created_v3", FeishuWebhookHandler())
        _webhook_service.register_handler("feishu", "contact.user.deleted_v3", FeishuWebhookHandler())
        _webhook_service.register_handler("wechat_work", "text", WeChatWorkWebhookHandler())
        _webhook_service.register_handler("wechat_work", "image", WeChatWorkWebhookHandler())
        _webhook_service.register_handler("wechat_work", "voice", WeChatWorkWebhookHandler())
        _webhook_service.register_handler("wechat_work", "event", WeChatWorkWebhookHandler())
    return _webhook_service


@router.post("/feishu")
async def handle_feishu_webhook(
    request: Request,
    x_feishu_signature: Optional[str] = Header(None),
    x_feishu_timestamp: Optional[str] = Header(None)
):
    """处理飞书Webhook"""
    webhook_service = get_webhook_service()

    try:
        body = await request.body()
        payload = await request.json()

        result = await webhook_service.handle_webhook(
            provider="feishu",
            payload=payload,
            headers={
                "signature": x_feishu_signature,
                "timestamp": x_feishu_timestamp
            }
        )

        return result
    except (RuntimeError, ValueError, TypeError, AttributeError) as e:
        logger.exception("Failed to handle Feishu webhook: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to handle webhook"
        )


@router.post("/wechat-work")
async def handle_wechat_work_webhook(
    request: Request,
    msg_signature: Optional[str] = Header(None),
    timestamp: Optional[str] = Header(None),
    nonce: Optional[str] = Header(None)
):
    """处理企业微信Webhook"""
    webhook_service = get_webhook_service()

    try:
        payload = await request.json()

        result = await webhook_service.handle_webhook(
            provider="wechat_work",
            payload=payload,
            headers={
                "signature": msg_signature,
                "timestamp": timestamp,
                "nonce": nonce
            }
        )

        return result
    except (RuntimeError, ValueError, TypeError, AttributeError) as e:
        logger.exception("Failed to handle WeChat Work webhook: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to handle webhook"
        )


@router.post("/{provider}")
async def handle_generic_webhook(
    provider: str,
    request: Request,
    event_type: str = Query(...)
):
    """处理通用Webhook"""
    webhook_service = get_webhook_service()

    try:
        payload = await request.json()

        result = await webhook_service.handle_webhook(
            provider=provider,
            payload=payload
        )

        return result
    except (RuntimeError, ValueError, TypeError, AttributeError) as e:
        logger.exception("Failed to handle generic webhook for %s: %s", provider, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to handle webhook"
        )


@router.get("/feishu/challenge")
async def verify_feishu_webhook(
    challenge: str = Query(...),
    verification_token: str = Query(...),
    type: str = Query(...),
    timestamp: str = Query(...)
):
    """验证飞书Webhook（用于设置回调URL）"""
    return {
        "challenge": challenge
    }
