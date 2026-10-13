"""素材来源获取与存储服务。"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import Asset, AssetStatus
from infrastructure.storage.asset_storage import LocalAssetStorage
from services.impl.asset_service import AssetServiceImpl
from services.impl.document_service import DocumentServiceImpl
from services.impl.safe_fetcher import SafeFetcher


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AssetIngestionService:
    def __init__(self, session: AsyncSession, fetcher: SafeFetcher | None = None, storage: LocalAssetStorage | None = None):
        self.session = session
        self.fetcher = fetcher or SafeFetcher()
        self.storage = storage or LocalAssetStorage()
        self.asset_service = AssetServiceImpl(session)

    async def _sync_legacy_document(self, asset: Asset) -> str | None:
        """为已绑定 Dataset 的素材建立唯一兼容 Document 记录。"""
        if not asset.dataset_id or not asset.storage_key or asset.legacy_document_id:
            return str(asset.legacy_document_id) if asset.legacy_document_id else None
        suffix = Path(asset.title).suffix.lower()
        mime_types = {
            "application/pdf": ".pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
            "text/markdown": ".md",
            "text/html": ".html",
            "text/csv": ".csv",
            "text/plain": ".txt",
        }
        file_type = suffix or mime_types.get(asset.mime_type or "", ".txt")
        document = await DocumentServiceImpl(self.session).upload_document(
            dataset_id=UUID(str(asset.dataset_id)),
            file_path=str(self.storage.resolve_key(asset.storage_key)),
            file_name=asset.title,
            file_type=file_type,
            file_size=asset.size_bytes,
            metadata={
                "asset_id": str(asset.id),
                "source_uri": asset.source_uri,
                "content_hash": asset.content_hash,
            },
        )
        asset.legacy_document_id = UUID(str(document["id"]))
        return document["id"]

    async def ingest_url(self, *, asset_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool = False) -> dict:
        result = await self.session.execute(
            select(Asset).where(
                Asset.id == str(asset_id),
                Asset.tenant_id == str(tenant_id),
                Asset.deleted_at.is_(None),
            )
        )
        asset = result.scalar_one_or_none()
        if asset is None:
            raise LookupError("素材不存在")
        await self.asset_service._verify_workspace_access(
            UUID(str(asset.workspace_id)), tenant_id, user_id, is_superuser
        )
        if asset.source_type != "url" or not asset.source_uri:
            raise ValueError("只有带 source_uri 的 URL 素材支持当前导入流程")

        asset.status = AssetStatus.PROCESSING.value
        asset.processing_error = None
        await self.session.flush()
        try:
            fetched = await self.fetcher.fetch(asset.source_uri)
            storage_key = await self.storage.put(str(tenant_id), str(asset.id), fetched.content)
            asset.storage_key = storage_key
            asset.source_etag = fetched.etag
            asset.source_uri = fetched.url
            asset.mime_type = fetched.content_type
            asset.size_bytes = len(fetched.content)
            asset.content_hash = hashlib.sha256(fetched.content).hexdigest()
            document_id = await self._sync_legacy_document(asset)
            asset.status = AssetStatus.PROCESSING.value if document_id else AssetStatus.READY.value
            if not document_id:
                asset.processed_at = _utcnow()
            await self.session.flush()
            result = self.asset_service._serialize(asset)
            result["document_id"] = document_id
            return result
        except Exception as exc:
            asset.status = AssetStatus.FAILED.value
            asset.processing_error = str(exc)[:2000]
            await self.session.flush()
            raise

    async def ingest_bytes(
        self,
        *,
        asset_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        content: bytes,
        content_type: str | None = None,
        is_superuser: bool = False,
    ) -> dict:
        result = await self.session.execute(
            select(Asset).where(
                Asset.id == str(asset_id),
                Asset.tenant_id == str(tenant_id),
                Asset.deleted_at.is_(None),
            )
        )
        asset = result.scalar_one_or_none()
        if asset is None:
            raise LookupError("素材不存在")
        await self.asset_service._verify_workspace_access(
            UUID(str(asset.workspace_id)), tenant_id, user_id, is_superuser
        )
        if asset.source_type not in {"file", "text", "chat"}:
            raise ValueError("当前素材来源类型不支持文件内容导入")
        if not content:
            raise ValueError("素材内容不能为空")

        asset.status = AssetStatus.PROCESSING.value
        asset.processing_error = None
        await self.session.flush()
        try:
            asset.storage_key = await self.storage.put(str(tenant_id), str(asset.id), content)
            asset.mime_type = content_type or asset.mime_type
            asset.size_bytes = len(content)
            asset.content_hash = hashlib.sha256(content).hexdigest()
            document_id = await self._sync_legacy_document(asset)
            asset.status = AssetStatus.PROCESSING.value if document_id else AssetStatus.READY.value
            if not document_id:
                asset.processed_at = _utcnow()
            await self.session.flush()
            result = self.asset_service._serialize(asset)
            result["document_id"] = document_id
            return result
        except Exception as exc:
            asset.status = AssetStatus.FAILED.value
            asset.processing_error = str(exc)[:2000]
            await self.session.flush()
            raise
