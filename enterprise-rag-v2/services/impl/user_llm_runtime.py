"""解析当前用户的模型运行时配置。"""

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import UserAPIKey, UserConfig
from services.impl.content_credential_service import CredentialVault


SUPPORTED_REMOTE_PROVIDERS = {"deepseek", "openai"}


async def resolve_user_llm_runtime(session: AsyncSession, user_id: Optional[str]) -> dict[str, Any]:
    """读取用户默认密钥和模型偏好，仅供服务端本次模型调用使用。"""
    if not user_id:
        return {}

    config = await session.scalar(select(UserConfig).where(UserConfig.user_id == str(user_id)))
    model = str(config.llm_model or "").strip() if config else ""
    item = await session.scalar(
        select(UserAPIKey)
        .where(UserAPIKey.user_id == str(user_id), UserAPIKey.is_active.is_(True))
        .order_by(UserAPIKey.is_default.desc(), UserAPIKey.updated_at.desc())
    )
    if item is None:
        return {"model": model} if model else {}

    try:
        credentials = CredentialVault().decrypt(item.api_key_encrypted)
        api_key = str(credentials.get("api_key") or "").strip()
        provider = str(item.provider or "deepseek").strip().lower()
        if not api_key or provider not in SUPPORTED_REMOTE_PROVIDERS:
            return {"model": model} if model else {}
        return {
            "provider": provider,
            "api_key": api_key,
            "base_url": str(item.base_url or "").strip(),
            "model": model,
        }
    except (RuntimeError, ValueError, TypeError, KeyError):
        return {"model": model} if model else {}
