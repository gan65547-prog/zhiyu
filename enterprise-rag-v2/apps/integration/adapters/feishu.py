"""
飞书适配器

处理飞书平台的消息接收和发送
"""

import json
import hashlib
import time
from typing import Dict, Any, Optional
import httpx

from .base import MessageAdapter, Message
from infrastructure.logging.logger import get_logger


logger = get_logger(__name__)


class FeishuAdapter(MessageAdapter):
    """飞书适配器"""
    
    def __init__(self, app_id: str, app_secret: str, verification_token: str, encrypt_key: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token
        self.encrypt_key = encrypt_key
        self.base_url = "https://open.feishu.cn/open-apis"
        self.token_cache = None
        self.token_expire_time = 0
    
    async def verify_signature(self, request: Dict[str, Any]) -> bool:
        """验证飞书签名"""
        timestamp = request.get("timestamp")
        nonce = request.get("nonce")
        signature = request.get("signature")
        
        if not all([timestamp, nonce, signature]):
            return False
        
        # 计算签名
        expected_signature = self._calculate_signature(timestamp, nonce, self.verification_token)
        return expected_signature == signature
    
    async def parse_message(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """解析飞书消息"""
        event = request.get("event", {})
        message = event.get("message", {})
        
        message_id = message.get("message_id")
        message_type = message.get("message_type")
        content = message.get("content", "{}")
        
        # 解析内容
        content_dict = json.loads(content)
        text = content_dict.get("text", "")
        
        # 获取发送者信息
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {})
        open_id = sender_id.get("open_id")
        user_id = sender_id.get("user_id")
        
        # 构建消息对象
        msg = Message(
            message_id=message_id,
            platform="feishu",
            user_id=open_id or user_id,
            content=text,
            message_type=message_type,
            conversation_id=event.get("conversation_id"),
            metadata={
                "sender": sender,
                "event_type": event.get("type"),
                "chat_type": event.get("chat_type")
            }
        )
        
        return msg.to_dict()
    
    async def send_message(self, user_id: str, content: str, **kwargs) -> bool:
        """发送飞书消息

        支持私聊和群聊两种场景:
        - 私聊: receive_id_type=open_id, receive_id=user_id(open_id)
        - 群聊: receive_id_type=chat_id, receive_id=chat_id
        """
        try:
            access_token = await self._get_access_token()
            if not access_token:
                logger.warning("[Feishu Adapter] access_token 获取失败，无法发送消息")
                return False

            chat_id = kwargs.get("chat_id")
            chat_type = kwargs.get("chat_type")

            # 判断发送目标: 群聊用 chat_id，私聊用 open_id
            if chat_id and chat_type == "group":
                receive_id_type = "chat_id"
                receive_id = chat_id
                logger.info("[Feishu Adapter] 检测到群聊消息，使用 chat_id 回复: %s", chat_id)
            else:
                receive_id_type = "open_id"
                receive_id = user_id

            payload = {
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({
                    "text": content
                })
            }

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            logger.info("[Feishu Adapter] 发送消息: receive_id=%s, receive_id_type=%s", receive_id, receive_id_type)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/im/v1/messages?receive_id_type={receive_id_type}",
                    headers=headers,
                    json=payload
                )

            if response.status_code != 200:
                logger.warning(
                    "[Feishu Adapter] 发送失败: status=%s, body=%s",
                    response.status_code, response.text[:500]
                )
                return False

            logger.info("[Feishu Adapter] 发送成功: receive_id=%s", receive_id)
            return True

        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error("[Feishu Adapter] 发送飞书消息失败: %s", e, exc_info=True)
            return False
    
    async def send_card_message(self, user_id: str, card: Dict[str, Any], **kwargs) -> bool:
        """发送飞书交互式卡片消息

        支持私聊和群聊两种场景:
        - 私聊: receive_id_type=open_id, receive_id=user_id(open_id)
        - 群聊: receive_id_type=chat_id, receive_id=chat_id

        Args:
            user_id: 用户 open_id
            card: 飞书卡片 JSON 对象（非字符串，非 content 包装）
            **kwargs: chat_id, chat_type
        """
        try:
            access_token = await self._get_access_token()
            if not access_token:
                logger.warning("[Feishu Adapter] access_token 获取失败，无法发送卡片消息")
                return False

            chat_id = kwargs.get("chat_id")
            chat_type = kwargs.get("chat_type")

            if chat_id and chat_type == "group":
                receive_id_type = "chat_id"
                receive_id = chat_id
            else:
                receive_id_type = "open_id"
                receive_id = user_id

            payload = {
                "receive_id": receive_id,
                "msg_type": "interactive",
                "content": json.dumps(card, ensure_ascii=False),
            }

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            logger.info("[Feishu Adapter] 发送卡片: receive_id=%s, type=%s", receive_id, receive_id_type)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/im/v1/messages?receive_id_type={receive_id_type}",
                    headers=headers,
                    json=payload,
                )

            if response.status_code != 200:
                logger.warning(
                    "[Feishu Adapter] 卡片发送失败: status=%s, body=%s",
                    response.status_code, response.text[:500],
                )
                return False

            logger.info("[Feishu Adapter] 卡片发送成功: receive_id=%s", receive_id)
            return True

        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error("[Feishu Adapter] 发送卡片消息失败: %s", e, exc_info=True)
            return False

    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取飞书用户信息"""
        try:
            access_token = await self._get_access_token()
            if not access_token:
                return None
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/contact/v3/users/{user_id}",
                    headers=headers,
                    params={"user_id_type": "open_id"}
                )
                
            if response.status_code == 200:
                data = response.json()
                user_info = data.get("data", {})
                return {
                    "name": user_info.get("name"),
                    "email": user_info.get("email"),
                    "avatar_url": user_info.get("avatar_url")
                }
            
        except (httpx.HTTPError, json.JSONDecodeError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning("获取飞书用户信息失败: %s", e)
        
        return None
    
    def _calculate_signature(self, timestamp: str, nonce: str, token: str) -> str:
        """计算签名"""
        items = [token, timestamp, nonce]
        items.sort()
        s = "".join(items)
        return hashlib.sha256(s.encode()).hexdigest()
    
    async def _get_access_token(self) -> str:
        """获取访问令牌"""
        current_time = time.time()
        
        # 检查令牌是否有效
        if self.token_cache and current_time < self.token_expire_time:
            return self.token_cache
        
        # 获取新令牌
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/auth/v3/app_access_token/internal",
                    json={
                        "app_id": self.app_id,
                        "app_secret": self.app_secret
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    code = data.get("code")
                    if code != 0:
                        logger.warning("[Feishu Adapter] 获取 token 失败: code=%s, msg=%s", code, data.get("msg"))
                        return None
                    self.token_cache = data.get("app_access_token")
                    expires_in = data.get("expire", 3600)
                    self.token_expire_time = current_time + expires_in - 300  # 提前5分钟过期
                    return self.token_cache

        except (httpx.HTTPError, json.JSONDecodeError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error("获取飞书访问令牌失败: %s", e)
        
        return None
