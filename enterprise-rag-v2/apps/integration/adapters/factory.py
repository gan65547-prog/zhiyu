"""
适配器工厂

根据平台类型创建相应的适配器实例
"""

from typing import Dict, Any, Optional

from .base import MessageAdapter
from .feishu import FeishuAdapter
from .wecom import WecomAdapter


class AdapterFactory:
    """适配器工厂"""
    
    @staticmethod
    def create_adapter(platform: str, config: Dict[str, Any]) -> Optional[MessageAdapter]:
        """
        创建适配器实例
        
        Args:
            platform: 平台类型 (feishu|wecom|wechat|qq|dingtalk)
            config: 平台配置
            
        Returns:
            MessageAdapter实例
        """
        
        if platform == "feishu":
            return FeishuAdapter(
                app_id=config.get("app_id"),
                app_secret=config.get("app_secret"),
                verification_token=config.get("verification_token"),
                encrypt_key=config.get("encrypt_key")
            )
        
        elif platform == "wecom":
            return WecomAdapter(
                corp_id=config.get("corp_id"),
                agent_id=config.get("agent_id"),
                agent_secret=config.get("agent_secret"),
                token=config.get("token"),
                encoding_aes_key=config.get("encoding_aes_key")
            )
        
        # 后续可以添加其他平台的适配器
        # elif platform == "wechat":
        #     return WechatAdapter(...)
        # elif platform == "qq":
        #     return QQAdapter(...)
        # elif platform == "dingtalk":
        #     return DingTalkAdapter(...)
        
        return None
