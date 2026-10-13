"""
企业微信适配器

处理企业微信平台的消息接收和发送
"""

import json
import hashlib
import time
from typing import Dict, Any, Optional
import httpx

from .base import MessageAdapter, Message
from infrastructure.logging.logger import get_logger


logger = get_logger(__name__)


class WecomAdapter(MessageAdapter):
    """企业微信适配器"""
    
    def __init__(self, corp_id: str, agent_id: str, agent_secret: str, token: str, encoding_aes_key: str):
        self.corp_id = corp_id
        self.agent_id = agent_id
        self.agent_secret = agent_secret
        self.token = token
        self.encoding_aes_key = encoding_aes_key
        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"
        self.token_cache = None
        self.token_expire_time = 0
    
    async def verify_signature(self, request: Dict[str, Any]) -> bool:
        """验证企业微信签名"""
        signature = request.get("signature")
        timestamp = request.get("timestamp")
        nonce = request.get("nonce")
        
        if not all([signature, timestamp, nonce]):
            return False
        
        # 计算签名
        expected_signature = self._calculate_signature(timestamp, nonce, self.token)
        return expected_signature == signature
    
    async def parse_message(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """解析企业微信消息"""
        # 企业微信消息格式为XML，这里简化处理
        # 实际实现需要解析XML
        msg_type = request.get("MsgType", "text")
        content = request.get("Content", "")
        from_user_name = request.get("FromUserName")
        msg_id = request.get("MsgId")
        
        # 构建消息对象
        msg = Message(
            message_id=msg_id,
            platform="wecom",
            user_id=from_user_name,
            content=content,
            message_type=msg_type,
            conversation_id=request.get("FromUserName"),  # 企业微信使用用户ID作为会话ID
            metadata={
                "agent_id": request.get("AgentID"),
                "create_time": request.get("CreateTime")
            }
        )
        
        return msg.to_dict()
    
    async def send_message(self, user_id: str, content: str, **kwargs) -> bool:
        """发送企业微信消息"""
        try:
            access_token = await self._get_access_token()
            if not access_token:
                logger.warning("企业微信 access_token 获取失败，无法发送消息")
                return False
            
            payload = {
                "touser": user_id,
                "msgtype": "text",
                "agentid": self.agent_id,
                "text": {
                    "content": content
                }
            }
            
            headers = {
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/message/send?access_token={access_token}",
                    json=payload,
                    headers=headers
                )
                
            data = response.json()
            return data.get("errcode") == 0
            
        except (httpx.HTTPError, json.JSONDecodeError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error("发送企业微信消息失败: %s", e, exc_info=True)
            return False
    
    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取企业微信用户信息"""
        try:
            access_token = await self._get_access_token()
            if not access_token:
                return None
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/user/get?access_token={access_token}&userid={user_id}"
                )
                
            if response.status_code == 200:
                data = response.json()
                if data.get("errcode") == 0:
                    return {
                        "name": data.get("name"),
                        "email": data.get("email"),
                        "avatar_url": data.get("avatar")
                    }
            
        except (httpx.HTTPError, json.JSONDecodeError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning("获取企业微信用户信息失败: %s", e)
        
        return None
    
    def _calculate_signature(self, timestamp: str, nonce: str, token: str) -> str:
        """计算签名"""
        items = [token, timestamp, nonce]
        items.sort()
        s = "".join(items)
        return hashlib.sha1(s.encode()).hexdigest()
    
    async def _get_access_token(self) -> str:
        """获取访问令牌"""
        current_time = time.time()
        
        # 检查令牌是否有效
        if self.token_cache and current_time < self.token_expire_time:
            return self.token_cache
        
        # 获取新令牌
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/gettoken",
                    params={
                        "corpid": self.corp_id,
                        "corpsecret": self.agent_secret
                    }
                )
                
            if response.status_code == 200:
                data = response.json()
                if data.get("errcode") == 0:
                    self.token_cache = data.get("access_token")
                    expires_in = data.get("expires_in", 7200)
                    self.token_expire_time = current_time + expires_in - 300  # 提前5分钟过期
                    return self.token_cache
            
        except (httpx.HTTPError, json.JSONDecodeError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error("获取企业微信访问令牌失败: %s", e)
        
        raise RuntimeError("无法获取企业微信访问令牌")
