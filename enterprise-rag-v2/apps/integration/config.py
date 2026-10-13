"""
集成模块配置类
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Dict, Any


class PlatformConfig(BaseSettings):
    """平台配置基类"""
    enabled: bool = False


class FeishuConfig(PlatformConfig):
    """飞书配置"""
    app_id: Optional[str] = None
    app_secret: Optional[str] = None
    verification_token: Optional[str] = None
    encrypt_key: Optional[str] = None


class WecomConfig(PlatformConfig):
    """企业微信配置"""
    corp_id: Optional[str] = None
    agent_id: Optional[str] = None
    agent_secret: Optional[str] = None
    token: Optional[str] = None
    encoding_aes_key: Optional[str] = None


class WechatConfig(PlatformConfig):
    """微信配置"""
    app_id: Optional[str] = None
    app_secret: Optional[str] = None
    token: Optional[str] = None
    encoding_aes_key: Optional[str] = None


class IntegrationSettings(BaseSettings):
    """集成模块配置"""

    model_config = SettingsConfigDict(
        env_prefix="INTEGRATION_",
        env_file=".env",
        extra="ignore"
    )

    # OpenClaw ↔ FastAPI 通信密钥
    integration_secret: str = "change-me-in-production"

    # 集成服务端口 (仅用于日志显示，实际端口由main.py控制)
    integration_port: int = 8000

    # 默认知识库ID (新用户首次使用时分配)
    default_dataset_id: int = 1

    # 用户自动注册开关
    auto_register_enabled: bool = True

    # 默认租户ID (单租户模式可忽略)
    default_tenant_id: int = 1

    # 配额统计维度
    quota_dimension_api_calls: str = "chat_messages_monthly"

    # 飞书配置 (直接在此定义，确保环境变量正确映射)
    feishu_app_id: Optional[str] = None
    feishu_app_secret: Optional[str] = None
    feishu_verification_token: Optional[str] = None
    feishu_encrypt_key: Optional[str] = None

    @property
    def feishu(self) -> FeishuConfig:
        """获取飞书配置"""
        return FeishuConfig(
            enabled=bool(self.feishu_app_id),
            app_id=self.feishu_app_id,
            app_secret=self.feishu_app_secret,
            verification_token=self.feishu_verification_token,
            encrypt_key=self.feishu_encrypt_key
        )

    # 平台配置 (保留用于其他平台)
    wecom: WecomConfig = WecomConfig()
    wechat: WechatConfig = WechatConfig()

    @property
    def platform_configs(self) -> Dict[str, Dict[str, Any]]:
        """获取所有平台配置"""
        return {
            "feishu": {
                "app_id": self.feishu_app_id,
                "app_secret": self.feishu_app_secret,
                "verification_token": self.feishu_verification_token,
                "encrypt_key": self.feishu_encrypt_key
            },
            "wecom": {
                "corp_id": self.wecom.corp_id,
                "agent_id": self.wecom.agent_id,
                "agent_secret": self.wecom.agent_secret,
                "token": self.wecom.token,
                "encoding_aes_key": self.wecom.encoding_aes_key
            },
            "wechat": {
                "app_id": self.wechat.app_id,
                "app_secret": self.wechat.app_secret,
                "token": self.wechat.token,
                "encoding_aes_key": self.wechat.encoding_aes_key
            }
        }


settings = IntegrationSettings()
