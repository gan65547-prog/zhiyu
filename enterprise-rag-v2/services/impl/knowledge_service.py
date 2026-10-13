"""知识卡片与证据绑定服务。

知识项只管理用户可审核的结构化结论；原文和检索链路仍归素材/文档领域所有。
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import (
    Asset,
    Document,
    DocumentChunk,
    KnowledgeEvidence,
    KnowledgeItem,
    KnowledgeItemVersion,
    ResearchEvidence,
)
from services.impl.asset_service import AssetServiceImpl
from services.impl.knowledge_backflow_service import KnowledgeBackflowService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeService:
    """知识中心应用服务，所有读写都以租户和工作空间为边界。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.access = AssetServiceImpl(session)

    @staticmethod
    def _evidence_dict(evidence: KnowledgeEvidence) -> dict[str, Any]:
        return {
            "id": evidence.id,
            "knowledge_item_id": evidence.knowledge_item_id,
            "asset_id": evidence.asset_id,
            "document_id": evidence.document_id,
            "chunk_id": evidence.chunk_id,
            "research_evidence_id": evidence.research_evidence_id,
            "quote": evidence.quote,
            "locator": evidence.locator,
            "source_uri": evidence.source_uri,
            "created_by": evidence.created_by,
            "created_at": evidence.created_at,
        }

    @classmethod
    def _item_dict(cls, item: KnowledgeItem, evidence: list[KnowledgeEvidence]) -> dict[str, Any]:
        return {
            "id": item.id,
            "tenant_id": item.tenant_id,
            "workspace_id": item.workspace_id,
            "created_by": item.created_by,
            "title": item.title,
            "item_type": item.item_type,
            "definition": item.definition,
            "details": item.details,
            "conclusions": list(item.conclusions or []),
            "confidence": item.confidence,
            "review_status": item.review_status,
            "reviewer_id": item.reviewer_id,
            "reviewed_at": item.reviewed_at,
            "metadata": dict(item.extra_metadata or {}),
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "evidence": [cls._evidence_dict(row) for row in evidence],
        }

    @staticmethod
    def _version_dict(version: KnowledgeItemVersion) -> dict[str, Any]:
        return {
            "id": version.id, "knowledge_item_id": version.knowledge_item_id,
            "version": version.version, "title": version.title, "item_type": version.item_type,
            "definition": version.definition, "details": version.details,
            "conclusions": list(version.conclusions or []), "confidence": version.confidence,
            "metadata": dict(version.extra_metadata or {}), "created_by": version.created_by,
            "created_at": version.created_at,
        }

    async def _record_version(self, item: KnowledgeItem, user_id: UUID) -> KnowledgeItemVersion:
        current = await self.session.scalar(
            select(func.max(KnowledgeItemVersion.version)).where(
                KnowledgeItemVersion.knowledge_item_id == str(item.id)
            )
        )
        version = KnowledgeItemVersion(
            tenant_id=item.tenant_id, workspace_id=item.workspace_id, knowledge_item_id=item.id,
            version=int(current or 0) + 1, title=item.title, item_type=item.item_type,
            definition=item.definition, details=item.details, conclusions=list(item.conclusions or []),
            confidence=item.confidence, extra_metadata=dict(item.extra_metadata or {}), created_by=str(user_id),
        )
        self.session.add(version)
        await self.session.flush()
        return version

    async def _get_item(self, item_id: UUID, tenant_id: UUID) -> Optional[KnowledgeItem]:
        result = await self.session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.id == str(item_id),
                KnowledgeItem.tenant_id == str(tenant_id),
                KnowledgeItem.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _load_evidence(self, item_id: UUID) -> list[KnowledgeEvidence]:
        result = await self.session.execute(
            select(KnowledgeEvidence)
            .where(KnowledgeEvidence.knowledge_item_id == str(item_id))
            .order_by(KnowledgeEvidence.created_at.asc())
        )
        return list(result.scalars().all())

    async def _verify_source(
        self,
        *,
        tenant_id: UUID,
        workspace_id: UUID,
        asset_id: UUID | None,
        document_id: UUID | None,
        chunk_id: UUID | None,
        research_evidence_id: UUID | None = None,
    ) -> None:
        if not any((asset_id, document_id, chunk_id, research_evidence_id)):
            raise ValueError("证据必须绑定素材、文档、文档分块或研究证据")
        if research_evidence_id:
            evidence_result = await self.session.execute(
                select(ResearchEvidence.id).where(
                    ResearchEvidence.id == str(research_evidence_id),
                    ResearchEvidence.tenant_id == str(tenant_id),
                    ResearchEvidence.workspace_id == str(workspace_id),
                )
            )
            if evidence_result.scalar_one_or_none() is None:
                raise PermissionError("研究证据不存在或不属于当前工作空间")
        if asset_id:
            asset_result = await self.session.execute(
                select(Asset.id).where(
                    Asset.id == str(asset_id),
                    Asset.tenant_id == str(tenant_id),
                    Asset.workspace_id == str(workspace_id),
                    Asset.deleted_at.is_(None),
                )
            )
            if asset_result.scalar_one_or_none() is None:
                raise PermissionError("证据素材不存在或无权访问")
        if document_id:
            document_result = await self.session.execute(
                select(Document.id).where(
                    Document.id == str(document_id),
                    Document.dataset.has(workspace_id=str(workspace_id)),
                )
            )
            if document_result.scalar_one_or_none() is None:
                raise PermissionError("证据文档不存在或不属于当前工作空间")
        if chunk_id:
            chunk_result = await self.session.execute(
                select(DocumentChunk.id).join(Document).where(
                    DocumentChunk.id == str(chunk_id),
                    Document.dataset.has(workspace_id=str(workspace_id)),
                )
            )
            if chunk_result.scalar_one_or_none() is None:
                raise PermissionError("证据分块不存在或不属于当前工作空间")

    async def create_item(self, *, tenant_id: UUID, user_id: UUID, is_superuser: bool, **data: Any) -> dict[str, Any]:
        workspace_id = data.pop("workspace_id")
        metadata = data.pop("metadata", None)
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        item = KnowledgeItem(
            tenant_id=str(tenant_id), workspace_id=str(workspace_id), created_by=str(user_id),
            extra_metadata=metadata or {}, **data
        )
        self.session.add(item)
        await self.session.flush()
        await self._record_version(item, user_id)
        return self._item_dict(item, [])

    async def list_items(
        self, *, tenant_id: UUID, workspace_id: UUID, user_id: UUID, page: int, page_size: int,
        review_status: str | None, is_superuser: bool,
    ) -> dict[str, Any]:
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        conditions = [
            KnowledgeItem.tenant_id == str(tenant_id),
            KnowledgeItem.workspace_id == str(workspace_id),
            KnowledgeItem.deleted_at.is_(None),
        ]
        if review_status:
            conditions.append(KnowledgeItem.review_status == review_status)
        total = await self.session.scalar(select(func.count(KnowledgeItem.id)).where(*conditions)) or 0
        result = await self.session.execute(
            select(KnowledgeItem).where(*conditions)
            .order_by(KnowledgeItem.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )
        items = []
        for item in result.scalars().all():
            items.append(self._item_dict(item, await self._load_evidence(item.id)))
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def get_item(self, *, item_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[dict[str, Any]]:
        item = await self._get_item(item_id, tenant_id)
        if item is None:
            return None
        await self.access._verify_workspace_access(UUID(str(item.workspace_id)), tenant_id, user_id, is_superuser)
        return self._item_dict(item, await self._load_evidence(item.id))

    async def update_item(self, *, item_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, changes: dict[str, Any]) -> Optional[dict[str, Any]]:
        item = await self._get_item(item_id, tenant_id)
        if item is None:
            return None
        await self.access._verify_workspace_access(UUID(str(item.workspace_id)), tenant_id, user_id, is_superuser)
        content_changed = False
        for key, value in changes.items():
            if value is not None and hasattr(item, key):
                setattr(item, key, value)
                content_changed = True
        if content_changed:
            item.review_status, item.reviewer_id, item.reviewed_at = "draft", None, None
        await self.session.flush()
        await self._record_version(item, user_id)
        result = self._item_dict(item, await self._load_evidence(item.id))
        if content_changed:
            await KnowledgeBackflowService(self.session).remove_from_rag(item)
        return result

    async def list_versions(self, *, item_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[list[dict[str, Any]]]:
        item = await self._get_item(item_id, tenant_id)
        if item is None:
            return None
        await self.access._verify_workspace_access(UUID(str(item.workspace_id)), tenant_id, user_id, is_superuser)
        result = await self.session.execute(
            select(KnowledgeItemVersion).where(
                KnowledgeItemVersion.knowledge_item_id == str(item.id),
                KnowledgeItemVersion.tenant_id == str(tenant_id),
            ).order_by(KnowledgeItemVersion.version.desc())
        )
        return [self._version_dict(row) for row in result.scalars().all()]

    async def rollback_item(self, *, item_id: UUID, version_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[dict[str, Any]]:
        item = await self._get_item(item_id, tenant_id)
        if item is None:
            return None
        await self.access._verify_workspace_access(UUID(str(item.workspace_id)), tenant_id, user_id, is_superuser)
        version = await self.session.scalar(select(KnowledgeItemVersion).where(
            KnowledgeItemVersion.id == str(version_id), KnowledgeItemVersion.knowledge_item_id == str(item.id),
            KnowledgeItemVersion.tenant_id == str(tenant_id),
        ))
        if version is None:
            raise ValueError("知识卡片版本不存在")
        item.title, item.item_type = version.title, version.item_type
        item.definition, item.details = version.definition, version.details
        item.conclusions, item.confidence = list(version.conclusions or []), version.confidence
        item.extra_metadata = dict(version.extra_metadata or {})
        item.review_status, item.reviewer_id, item.reviewed_at = "draft", None, None
        await self.session.flush()
        await self._record_version(item, user_id)
        result = self._item_dict(item, await self._load_evidence(item.id))
        await KnowledgeBackflowService(self.session).remove_from_rag(item)
        return result

    async def review_item(self, *, item_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, review_status: str) -> Optional[dict[str, Any]]:
        item = await self._get_item(item_id, tenant_id)
        if item is None:
            return None
        await self.access._verify_workspace_access(UUID(str(item.workspace_id)), tenant_id, user_id, is_superuser)
        evidence = await self._load_evidence(item.id)
        if review_status == "approved" and not evidence:
            raise ValueError("没有证据的知识卡片不能审核通过")
        item.review_status = review_status
        item.reviewer_id = str(user_id)
        item.reviewed_at = _utcnow()
        await self.session.flush()
        result = self._item_dict(item, evidence)
        if review_status == "approved":
            await KnowledgeBackflowService(self.session).sync_to_rag(item, evidence=evidence)
        elif review_status in ("draft", "rejected"):
            # 审核退回 draft / 审核拒绝时同步移除已回流文档与向量，避免被推翻的结论继续被检索命中
            await KnowledgeBackflowService(self.session).remove_from_rag(item)
        return result

    async def add_evidence(self, *, item_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, **data: Any) -> Optional[dict[str, Any]]:
        item = await self._get_item(item_id, tenant_id)
        if item is None:
            return None
        workspace_id = UUID(str(item.workspace_id))
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        await self._verify_source(tenant_id=tenant_id, workspace_id=workspace_id, **{key: data.get(key) for key in ("asset_id", "document_id", "chunk_id", "research_evidence_id")})
        evidence = KnowledgeEvidence(
            tenant_id=str(tenant_id), workspace_id=str(workspace_id), knowledge_item_id=str(item.id),
            created_by=str(user_id), **data,
        )
        self.session.add(evidence)
        await self.session.flush()
        return self._evidence_dict(evidence)
