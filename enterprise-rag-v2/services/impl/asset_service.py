"""AI 工作台素材元数据服务。

本服务只负责素材登记和生命周期元数据，不在此处执行文件解析或 URL 抓取。
后续 ingestion worker 通过 Asset.id 接入现有 documents/RAG 链路。
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import (
    Asset,
    AssetSourceType,
    AssetStatus,
    Dataset,
    Workspace,
    WorkspaceMember,
    Document,
    IngestionBatch,
)
from infrastructure.storage.asset_storage import LocalAssetStorage
from services.impl.document_service import DocumentServiceImpl
from services.impl.document_indexing_service import DocumentIndexingService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AssetServiceImpl:
    """素材生命周期元数据服务，所有查询都带租户和工作空间约束。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _verify_workspace_access(
        self,
        workspace_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool = False,
    ) -> Workspace:
        workspace_result = await self.session.execute(
            select(Workspace).where(
                Workspace.id == str(workspace_id),
                Workspace.tenant_id == str(tenant_id),
            )
        )
        workspace = workspace_result.scalar_one_or_none()
        if workspace is None:
            raise PermissionError("工作空间不存在或不属于当前租户")

        if not is_superuser:
            member_result = await self.session.execute(
                select(WorkspaceMember.id).where(
                    WorkspaceMember.workspace_id == str(workspace_id),
                    WorkspaceMember.user_id == str(user_id),
                )
            )
            if member_result.scalar_one_or_none() is None:
                raise PermissionError("您不是该工作空间成员")
        return workspace

    @staticmethod
    def _serialize(asset: Asset) -> dict[str, Any]:
        return {
            "id": str(asset.id),
            "tenant_id": str(asset.tenant_id),
            "workspace_id": str(asset.workspace_id),
            "dataset_id": str(asset.dataset_id) if asset.dataset_id else None,
            "batch_id": str(asset.batch_id) if asset.batch_id else None,
            "created_by": str(asset.created_by),
            "legacy_document_id": str(asset.legacy_document_id) if asset.legacy_document_id else None,
            "source_type": asset.source_type,
            "title": asset.title,
            "source_uri": asset.source_uri,
            "storage_key": asset.storage_key,
            "source_etag": asset.source_etag,
            "mime_type": asset.mime_type,
            "size_bytes": asset.size_bytes,
            "content_hash": asset.content_hash,
            "status": asset.status,
            "processing_error": asset.processing_error,
            "metadata": asset.extra_metadata or {},
            "created_at": asset.created_at.isoformat() if asset.created_at else None,
            "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
            "processed_at": asset.processed_at.isoformat() if asset.processed_at else None,
            "deleted_at": asset.deleted_at.isoformat() if asset.deleted_at else None,
        }

    async def create_asset(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        dataset_id: Optional[UUID] = None,
        batch_id: Optional[UUID] = None,
        user_id: UUID,
        source_type: str,
        title: str,
        source_uri: Optional[str] = None,
        mime_type: Optional[str] = None,
        size_bytes: int = 0,
        content_hash: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        is_superuser: bool = False,
    ) -> dict[str, Any]:
        await self._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        if dataset_id is None:
            dataset_id = await self.ensure_default_dataset(
                workspace_id=workspace_id, tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser
            )
        if dataset_id:
            dataset_result = await self.session.execute(
                select(Dataset).where(
                    Dataset.id == str(dataset_id),
                    Dataset.workspace_id == str(workspace_id),
                )
            )
            if dataset_result.scalar_one_or_none() is None:
                raise PermissionError("数据集不存在或不属于当前工作空间")
        try:
            source_type_value = AssetSourceType(source_type)
        except ValueError as exc:
            raise ValueError(f"不支持的素材来源类型: {source_type}") from exc
        if source_type_value == AssetSourceType.URL and not source_uri:
            raise ValueError("URL 素材必须提供 source_uri")

        asset = Asset(
            tenant_id=str(tenant_id),
            workspace_id=str(workspace_id),
            dataset_id=str(dataset_id) if dataset_id else None,
            batch_id=str(batch_id) if batch_id else None,
            created_by=str(user_id),
            source_type=source_type_value.value,
            title=title.strip(),
            source_uri=source_uri,
            mime_type=mime_type,
            size_bytes=size_bytes,
            content_hash=content_hash,
            status=AssetStatus.PENDING.value,
            extra_metadata=metadata or {},
        )
        self.session.add(asset)
        await self.session.flush()
        return self._serialize(asset)

    async def ensure_default_dataset(
        self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool = False
    ) -> UUID:
        """为首次导入准备一个可以直接问答的默认资料库。"""
        await self._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        result = await self.session.execute(
            select(Dataset).where(Dataset.workspace_id == str(workspace_id)).order_by(Dataset.created_at.asc())
        )
        datasets = list(result.scalars().all())
        for dataset in datasets:
            if (dataset.extra_metadata or {}).get("system_default") is True:
                return UUID(str(dataset.id))
        if datasets:
            return UUID(str(datasets[0].id))
        dataset = Dataset(
            workspace_id=str(workspace_id),
            name="我的资料库",
            description="首次导入资料的默认知识库",
            embedding_model="bge-small-zh-v1.5",
            chunk_size=500,
            chunk_overlap=50,
            extra_metadata={"system_default": True, "created_by": str(user_id)},
        )
        self.session.add(dataset)
        await self.session.flush()
        return UUID(str(dataset.id))

    async def bind_agent_run(self, *, asset_id: UUID, tenant_id: UUID, user_id: UUID, agent_run_id: UUID, is_superuser: bool = False) -> None:
        """绑定素材整理 Agent 运行；保持 Agent 编排和素材元数据的事务边界。"""
        result = await self.session.execute(select(Asset).where(Asset.id == str(asset_id), Asset.tenant_id == str(tenant_id), Asset.deleted_at.is_(None)))
        asset = result.scalar_one_or_none()
        if asset is None:
            raise LookupError("素材不存在")
        await self._verify_workspace_access(UUID(str(asset.workspace_id)), tenant_id, user_id, is_superuser)
        metadata = dict(asset.extra_metadata or {})
        metadata["organize_agent_run_id"] = str(agent_run_id)
        asset.extra_metadata = metadata
        await self.session.flush()

    async def list_assets(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        asset_status: Optional[str] = None,
        is_superuser: bool = False,
    ) -> dict[str, Any]:
        await self._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        conditions = [
            Asset.tenant_id == str(tenant_id),
            Asset.workspace_id == str(workspace_id),
            Asset.deleted_at.is_(None),
        ]
        if asset_status:
            conditions.append(Asset.status == asset_status)
        count_result = await self.session.execute(
            select(Asset.id).where(*conditions)
        )
        total = len(count_result.all())
        result = await self.session.execute(
            select(Asset)
            .where(*conditions)
            .order_by(Asset.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return {
            "items": [self._serialize(item) for item in result.scalars().all()],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_asset(
        self,
        *,
        asset_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool = False,
    ) -> Optional[dict[str, Any]]:
        result = await self.session.execute(
            select(Asset).where(
                Asset.id == str(asset_id),
                Asset.tenant_id == str(tenant_id),
                Asset.deleted_at.is_(None),
            )
        )
        asset = result.scalar_one_or_none()
        if asset is None:
            return None
        await self._verify_workspace_access(
            UUID(str(asset.workspace_id)), tenant_id, user_id, is_superuser
        )
        return self._serialize(asset)

    async def delete_asset(
        self,
        *,
        asset_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool = False,
    ) -> bool:
        result = await self.session.execute(
            select(Asset).where(
                Asset.id == str(asset_id),
                Asset.tenant_id == str(tenant_id),
                Asset.deleted_at.is_(None),
            )
        )
        asset = result.scalar_one_or_none()
        if asset is None:
            return False
        await self._verify_workspace_access(
            UUID(str(asset.workspace_id)), tenant_id, user_id, is_superuser
        )
        if asset.legacy_document_id:
            document_id = UUID(str(asset.legacy_document_id))
            vectors_removed = await DocumentIndexingService(self.session).delete_document_vectors(
                document_id, workspace_id=str(asset.workspace_id)
            )
            if not vectors_removed:
                raise RuntimeError("素材关联的向量删除失败，已阻止删除以避免残留检索结果")
            await DocumentServiceImpl(self.session).delete_document(document_id)
        await LocalAssetStorage().delete(str(tenant_id), str(asset.id))
        asset.deleted_at = _utcnow()
        asset.status = AssetStatus.DELETED.value
        await self.session.flush()
        return True

    async def prepare_retry(
        self, *, asset_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool = False
    ) -> Optional[dict[str, Any]]:
        """校验并重置失败素材；实际处理由对应队列任务执行。"""
        result = await self.session.execute(
            select(Asset).where(
                Asset.id == str(asset_id),
                Asset.tenant_id == str(tenant_id),
                Asset.deleted_at.is_(None),
            )
        )
        asset = result.scalar_one_or_none()
        if asset is None:
            return None
        await self._verify_workspace_access(UUID(str(asset.workspace_id)), tenant_id, user_id, is_superuser)
        document = await self.session.get(Document, str(asset.legacy_document_id)) if asset.legacy_document_id else None
        is_stalled = asset.status == AssetStatus.PROCESSING.value and document is not None and str(document.status.value if hasattr(document.status, "value") else document.status).lower() in {"pending", "processing"}
        if asset.status != AssetStatus.FAILED.value and not is_stalled:
            raise ValueError("只有处理失败或已卡住的素材可以重试")
        metadata = dict(asset.extra_metadata or {})
        key = "recovery_count" if is_stalled else "retry_count"
        metadata[key] = int(metadata.get(key, 0)) + 1
        asset.extra_metadata = metadata
        asset.status = AssetStatus.PENDING.value
        asset.processing_error = None
        await self.session.flush()
        return self._serialize(asset)

    async def processing_status(
        self, *, asset_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool = False
    ) -> Optional[dict[str, Any]]:
        result = await self.session.execute(
            select(Asset).where(
                Asset.id == str(asset_id),
                Asset.tenant_id == str(tenant_id),
                Asset.deleted_at.is_(None),
            )
        )
        asset = result.scalar_one_or_none()
        if asset is None:
            return None
        await self._verify_workspace_access(UUID(str(asset.workspace_id)), tenant_id, user_id, is_superuser)
        document = await self.session.get(Document, str(asset.legacy_document_id)) if asset.legacy_document_id else None
        document_status = None
        progress = 0
        phase = None
        done_chunks = 0
        total_chunks = 0
        error = asset.processing_error
        stalled = False
        if document is not None:
            document_status = document.status.value if hasattr(document.status, "value") else str(document.status)
            metadata = (document.extra_metadata or {}).get("processing", {}) if isinstance(document.extra_metadata, dict) else {}
            progress = 100 if document_status == "completed" else int(metadata.get("progress", 0))
            phase = metadata.get("phase")
            done_chunks = int(metadata.get("done_chunks", 0))
            total_chunks = int(metadata.get("total_chunks", 0))
            error = error or metadata.get("error_reason")
            updated_at = asset.updated_at or asset.created_at
            if updated_at.tzinfo is None or updated_at.utcoffset() is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            age_seconds = (_utcnow() - updated_at).total_seconds()
            stalled = asset.status == AssetStatus.PROCESSING.value and document_status.lower() in {"pending", "processing"} and age_seconds >= 60
        return {
            "asset_id": asset.id,
            "status": asset.status,
            "progress": max(0, min(100, progress)),
            "phase": phase,
            "document_id": asset.legacy_document_id,
            "document_status": document_status,
            "done_chunks": done_chunks,
            "total_chunks": total_chunks,
            "stalled": stalled,
            "processing_error": error,
        }

    async def create_ingestion_batch(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        dataset_id: UUID,
        user_id: UUID,
        total_count: int,
        options_json: dict[str, Any],
    ) -> IngestionBatch:
        """创建导入批次记录（调用方负责后续 commit）。"""
        batch = IngestionBatch(
            tenant_id=str(tenant_id),
            workspace_id=str(workspace_id),
            dataset_id=str(dataset_id),
            created_by=str(user_id),
            total_count=total_count,
            options_json=options_json,
        )
        self.session.add(batch)
        await self.session.flush()
        return batch

    async def get_ingestion_batch(
        self,
        *,
        batch_id: UUID,
        workspace_id: UUID,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool = False,
    ) -> Optional[IngestionBatch]:
        """按租户/工作空间约束取批次；不存在返回 None，越权抛 PermissionError。"""
        result = await self.session.execute(
            select(IngestionBatch).where(
                IngestionBatch.id == str(batch_id),
                IngestionBatch.workspace_id == str(workspace_id),
                IngestionBatch.tenant_id == str(tenant_id),
            )
        )
        batch = result.scalar_one_or_none()
        if batch is None:
            return None
        await self._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        return batch

    async def build_batch_response(self, batch: IngestionBatch) -> dict[str, Any]:
        """汇总批次下素材状态并同步批次进度字段（调用方负责 commit）。"""
        result = await self.session.execute(
            select(Asset)
            .where(Asset.batch_id == str(batch.id), Asset.deleted_at.is_(None))
            .order_by(Asset.created_at.asc())
        )
        assets = list(result.scalars().all())
        statuses = [str(item.status) for item in assets]
        completed = sum(item == AssetStatus.READY.value for item in statuses)
        failed = sum(item == AssetStatus.FAILED.value for item in statuses)
        if assets and completed + failed == len(assets):
            batch.status = "failed" if failed == len(assets) else ("completed_with_errors" if failed else "completed")
            batch.completed_at = batch.completed_at or _utcnow()
        else:
            batch.status = "processing"
            batch.completed_at = None
        batch.completed_count = completed
        batch.failed_count = failed
        return {
            "id": batch.id,
            "workspace_id": batch.workspace_id,
            "dataset_id": batch.dataset_id,
            "status": batch.status,
            "total_count": batch.total_count,
            "completed_count": completed,
            "failed_count": failed,
            "assets": [self._serialize(item) for item in assets],
            "created_at": batch.created_at,
            "updated_at": batch.updated_at,
            "completed_at": batch.completed_at,
        }

    async def mark_asset_failed(self, asset_id: str, error: str) -> None:
        """将素材标记为失败并记录处理错误（调用方负责 commit）。"""
        result = await self.session.execute(select(Asset).where(Asset.id == asset_id))
        asset = result.scalar_one_or_none()
        if asset is not None:
            asset.status = AssetStatus.FAILED.value
            asset.processing_error = error

    async def retry_batch_assets(
        self,
        *,
        batch: IngestionBatch,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool = False,
    ) -> list[str]:
        """重新提交批次中失败或已卡住的素材，返回待投递任务成功的素材 ID。"""
        result = await self.session.execute(
            select(Asset).where(
                Asset.batch_id == str(batch.id),
                Asset.deleted_at.is_(None),
                Asset.status.in_([AssetStatus.FAILED.value, AssetStatus.PROCESSING.value]),
            )
        )
        pending: list[str] = []
        for asset in result.scalars().all():
            document = await self.session.get(Document, str(asset.legacy_document_id)) if asset.legacy_document_id else None
            document_status = str(document.status.value if hasattr(document.status, "value") else document.status).lower() if document else ""
            is_stalled = asset.status == AssetStatus.PROCESSING.value and document_status in {"pending", "processing"}
            if asset.status != AssetStatus.FAILED.value and not is_stalled:
                continue
            retry_result = await self.prepare_retry(
                asset_id=UUID(str(asset.id)), tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser,
            )
            if retry_result:
                pending.append(str(asset.id))
        return pending
