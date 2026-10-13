"""内容发布凭据：加密保存、工作空间隔离、永不回传明文。"""

import json
import os
import base64
import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import ContentConnectorCredential
from services.impl.asset_service import AssetServiceImpl
from services.impl.content_connector_registry import ContentConnectorRegistry


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CredentialVault:
    def __init__(self, key: str | bytes | None = None):
        raw = key or os.getenv("ENCRYPTION_KEY")
        if not raw:
            raise RuntimeError("ENCRYPTION_KEY 未设置，不能保存内容平台凭据")
        raw_bytes = raw.encode() if isinstance(raw, str) else raw
        try:
            self.cipher = Fernet(raw_bytes)
        except (TypeError, ValueError):
            # 兼容历史部署中保存的高熵普通字符串，同时保持确定性和 32 字节密钥长度。
            # 新部署仍建议直接使用 Fernet.generate_key() 生成的标准 Base64 key。
            derived = base64.urlsafe_b64encode(hashlib.sha256(raw_bytes).digest())
            self.cipher = Fernet(derived)

    def encrypt(self, value: dict[str, Any]) -> str:
        return self.cipher.encrypt(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).decode()

    def decrypt(self, value: str) -> dict[str, Any]:
        return json.loads(self.cipher.decrypt(value.encode()).decode())


class ContentCredentialService:
    def __init__(self, session: AsyncSession, vault: CredentialVault | None = None):
        self.session = session
        self.vault = vault
        self.access = AssetServiceImpl(session)

    async def _check(self, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> None:
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)

    @staticmethod
    def _safe(item: ContentConnectorCredential) -> dict[str, Any]:
        return {"id": item.id, "workspace_id": item.workspace_id, "platform": item.platform, "name": item.name, "credential_hint": item.credential_hint, "status": item.status, "created_by": item.created_by, "last_used_at": item.last_used_at, "last_error": item.last_error, "created_at": item.created_at, "updated_at": item.updated_at}

    async def list(self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> list[dict[str, Any]]:
        await self._check(workspace_id, tenant_id, user_id, is_superuser)
        result = await self.session.execute(select(ContentConnectorCredential).where(ContentConnectorCredential.workspace_id == str(workspace_id), ContentConnectorCredential.tenant_id == str(tenant_id), ContentConnectorCredential.status != "deleted").order_by(ContentConnectorCredential.created_at.desc()))
        return [self._safe(item) for item in result.scalars().all()]

    async def create(self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, platform: str, name: str, credentials: dict[str, Any], hint: str | None = None) -> dict[str, Any]:
        await self._check(workspace_id, tenant_id, user_id, is_superuser)
        if not credentials or any(not isinstance(key, str) or not key.strip() for key in credentials):
            raise ValueError("凭据必须是非空键值对象")
        if len(json.dumps(credentials, ensure_ascii=False)) > 20000:
            raise ValueError("凭据内容超过 20KB 限制")
        item = ContentConnectorCredential(tenant_id=str(tenant_id), workspace_id=str(workspace_id), platform=platform.strip().lower(), name=name.strip(), encrypted_credentials=(self.vault or CredentialVault()).encrypt(credentials), credential_hint=(hint or "已配置")[:255], status="active", created_by=str(user_id), created_at=_utcnow(), updated_at=_utcnow())
        self.session.add(item)
        await self.session.flush()
        return self._safe(item)

    async def resolve(self, *, credential_id: str, workspace_id: str, tenant_id: str) -> tuple[ContentConnectorCredential, dict[str, Any]] | None:
        item = await self.session.scalar(select(ContentConnectorCredential).where(ContentConnectorCredential.id == credential_id, ContentConnectorCredential.workspace_id == workspace_id, ContentConnectorCredential.tenant_id == tenant_id, ContentConnectorCredential.status == "active"))
        if item is None:
            return None
        return item, (self.vault or CredentialVault()).decrypt(item.encrypted_credentials)

    async def test(self, *, credential_id: UUID, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> dict[str, Any] | None:
        """验证凭据可解密并报告连接器能力；未注册平台绝不发起外部请求。"""
        await self._check(workspace_id, tenant_id, user_id, is_superuser)
        resolved = await self.resolve(credential_id=str(credential_id), workspace_id=str(workspace_id), tenant_id=str(tenant_id))
        if resolved is None:
            return None
        item, credentials = resolved
        checked_at = _utcnow()
        connector = ContentConnectorRegistry().get(item.platform)
        if connector is None:
            item.last_error = "平台尚未注册自动连接器；当前仅支持人工发布和指标快照导入"
            item.updated_at = checked_at
            await self.session.flush()
            return {"credential_id": item.id, "platform": item.platform, "status": "not_supported", "message": item.last_error, "connector_registered": False, "checked_at": checked_at}
        if item.platform == "manual":
            item.last_error = None
            item.updated_at = checked_at
            await self.session.flush()
            message = "人工确认连接器可用；不需要外部平台凭据"
            result_status = "ready"
        elif hasattr(connector, "test_credentials"):
            result = await connector.test_credentials(credentials=credentials)
            result_status = str(result.get("status") or "failed")
            message = str(result.get("message") or "连接器凭据验证失败")
            item.last_error = None if result_status == "configured" else message[:500]
            item.updated_at = checked_at
            await self.session.flush()
        else:
            item.last_error = None
            item.updated_at = checked_at
            await self.session.flush()
            message = "凭据已解密且连接器已注册；当前未执行外部平台网络验证"
            result_status = "configured"
        return {"credential_id": item.id, "platform": item.platform, "status": result_status, "message": message, "connector_registered": True, "checked_at": checked_at}

    async def revoke(self, *, credential_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> dict[str, Any] | None:
        item = await self.session.scalar(select(ContentConnectorCredential).where(ContentConnectorCredential.id == str(credential_id), ContentConnectorCredential.tenant_id == str(tenant_id), ContentConnectorCredential.status != "deleted"))
        if item is None:
            return None
        await self._check(UUID(str(item.workspace_id)), tenant_id, user_id, is_superuser)
        item.status = "revoked"
        item.updated_at = _utcnow()
        await self.session.flush()
        return self._safe(item)
