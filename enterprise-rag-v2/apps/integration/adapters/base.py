"""
消息适配器基类

定义各平台消息适配器的统一接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime


class MessageAdapter(ABC):
    """消息适配器基类"""
    
    @abstractmethod
    async def verify_signature(self, request: Dict[str, Any]) -> bool:
        """验证请求签名"""
        pass
    
    @abstractmethod
    async def parse_message(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """解析消息"""
        pass
    
    @abstractmethod
    async def send_message(self, user_id: str, content: str, **kwargs) -> bool:
        """发送消息"""
        pass
    
    @abstractmethod
    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        pass


class Message:
    """统一消息模型"""
    def __init__(self,
                 message_id: str,
                 platform: str,
                 user_id: str,
                 content: str,
                 message_type: str = "text",
                 conversation_id: Optional[str] = None,
                 reply_to: Optional[str] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.message_id = message_id
        self.platform = platform
        self.user_id = user_id
        self.content = content
        self.message_type = message_type
        self.conversation_id = conversation_id
        self.reply_to = reply_to
        self.metadata = metadata or {}
        self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "message_id": self.message_id,
            "platform": self.platform,
            "user_id": self.user_id,
            "content": self.content,
            "message_type": self.message_type,
            "conversation_id": self.conversation_id,
            "reply_to": self.reply_to,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }
