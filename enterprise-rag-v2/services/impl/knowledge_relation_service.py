"""知识关系网络服务：只维护已审核知识卡片之间的显式边。"""

import json
import os
import re
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.interfaces.rag_engine import RetrievedDocument
from infrastructure.database.models import KnowledgeItem, KnowledgeRelation
from services.impl.asset_service import AssetServiceImpl
from core.rag.llm_provider import LLMProviderFactory
from services.impl.user_llm_runtime import resolve_user_llm_runtime


def _create_llm(provider: str, **kwargs: Any):
    """创建模型并兼容只接受 provider 的旧工厂替身。"""
    try:
        return LLMProviderFactory.create(provider, **kwargs)
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        return LLMProviderFactory.create(provider)


class KnowledgeRelationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.access = AssetServiceImpl(session)

    async def create(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool,
        workspace_id: UUID,
        source_item_id: UUID,
        target_item_id: UUID,
        relation_type: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        if source_item_id == target_item_id:
            raise ValueError("知识卡片不能关联自身")
        items = await self._load_items(tenant_id, workspace_id, [source_item_id, target_item_id])
        if len(items) != 2:
            raise PermissionError("关系节点不存在或不属于当前工作空间")
        if any(item.review_status != "approved" for item in items):
            raise ValueError("只有审核通过的知识卡片才能建立关系")
        duplicate = await self.session.scalar(
            select(KnowledgeRelation).where(
                KnowledgeRelation.tenant_id == str(tenant_id),
                KnowledgeRelation.workspace_id == str(workspace_id),
                KnowledgeRelation.source_item_id == str(source_item_id),
                KnowledgeRelation.target_item_id == str(target_item_id),
                KnowledgeRelation.relation_type == relation_type,
            )
        )
        if duplicate:
            return await self._relation_dict(duplicate)
        relation = KnowledgeRelation(
            tenant_id=str(tenant_id), workspace_id=str(workspace_id),
            source_item_id=str(source_item_id), target_item_id=str(target_item_id),
            relation_type=relation_type, description=description, created_by=str(user_id),
        )
        self.session.add(relation)
        await self.session.flush()
        return await self._relation_dict(relation)

    async def network(self, *, tenant_id: UUID, user_id: UUID, is_superuser: bool, workspace_id: UUID) -> dict[str, Any]:
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        item_result = await self.session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.tenant_id == str(tenant_id), KnowledgeItem.workspace_id == str(workspace_id),
                KnowledgeItem.deleted_at.is_(None), KnowledgeItem.review_status == "approved",
            ).order_by(KnowledgeItem.title.asc())
        )
        items = list(item_result.scalars().all())
        item_by_id = {str(item.id): item for item in items}
        relation_result = await self.session.execute(
            select(KnowledgeRelation).where(
                KnowledgeRelation.tenant_id == str(tenant_id), KnowledgeRelation.workspace_id == str(workspace_id),
                KnowledgeRelation.source_item_id.in_(list(item_by_id)), KnowledgeRelation.target_item_id.in_(list(item_by_id)),
            ).order_by(KnowledgeRelation.created_at.asc())
        )
        edges = [await self._relation_dict(row, item_by_id) for row in relation_result.scalars().all()]
        return {
            "nodes": [{"id": item.id, "title": item.title, "item_type": item.item_type, "confidence": item.confidence} for item in items],
            "edges": edges,
        }

    async def suggestions(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool,
        workspace_id: UUID,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """基于已审核知识的共享术语生成候选边，不自动写入正式关系。

        这是关系抽取的安全第一阶段：候选结果带匹配术语和分数，仍需人工确认，
        不允许草稿或跨工作空间节点进入网络。后续可替换为模型提取器而不改变 API。
        """
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        if not 1 <= int(limit) <= 100:
            raise ValueError("suggestion limit 必须在 1 到 100 之间")
        result = await self.session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.tenant_id == str(tenant_id), KnowledgeItem.workspace_id == str(workspace_id),
                KnowledgeItem.deleted_at.is_(None), KnowledgeItem.review_status == "approved",
            ).order_by(KnowledgeItem.created_at.asc()).limit(200)
        )
        items = list(result.scalars().all())
        if len(items) < 2:
            return []
        existing_result = await self.session.execute(
            select(KnowledgeRelation.source_item_id, KnowledgeRelation.target_item_id).where(
                KnowledgeRelation.tenant_id == str(tenant_id), KnowledgeRelation.workspace_id == str(workspace_id),
            )
        )
        existing = {(str(row[0]), str(row[1])) for row in existing_result.all()}
        term_sets = {str(item.id): self._terms(item) for item in items}
        candidates: list[dict[str, Any]] = []
        for index, source in enumerate(items):
            for target in items[index + 1:]:
                if (str(source.id), str(target.id)) in existing or (str(target.id), str(source.id)) in existing:
                    continue
                overlap = sorted(term_sets[str(source.id)] & term_sets[str(target.id)])
                if not overlap:
                    continue
                union = term_sets[str(source.id)] | term_sets[str(target.id)]
                score = round(len(overlap) / max(1, len(union)), 4)
                if score < 0.1:
                    continue
                candidates.append({
                    "source_item_id": source.id, "target_item_id": target.id,
                    "source_title": source.title, "target_title": target.title,
                    "relation_type": "related", "score": score,
                    "matched_terms": overlap[:12], "requires_human_review": True,
                })
        return sorted(candidates, key=lambda item: (-item["score"], str(item["source_item_id"])))[:int(limit)]

    async def model_suggestions(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        is_superuser: bool,
        workspace_id: UUID,
        limit: int = 20,
        provider: str | None = None,
        max_tokens: int = 1200,
    ) -> list[dict[str, Any]]:
        """让白名单模型提出候选边；只返回可校验的建议，不写入关系表。"""
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        if not 1 <= int(limit) <= 50:
            raise ValueError("model suggestion limit 必须在 1 到 50 之间")
        if not 128 <= int(max_tokens) <= 4000:
            raise ValueError("model suggestion max_tokens 必须在 128 到 4000 之间")
        items = await self._approved_items(tenant_id, workspace_id, 80)
        if len(items) < 2:
            return []
        existing = await self._existing_edges(tenant_id, workspace_id)
        documents = [RetrievedDocument(
            id=str(item.id), document_id=str(item.id), document_name=item.title,
            content=self._item_text(item)[:5000], metadata={"knowledge_item_id": str(item.id)},
            score=1.0, chunk_index=0,
        ) for item in items]
        prompt = self._model_prompt(items, limit)
        runtime = await resolve_user_llm_runtime(self.session, str(user_id))
        selected_provider = (provider or runtime.get("provider") or os.getenv("LLM_PROVIDER", "ollama")).strip().lower()
        if selected_provider == "ollama":
            llm = _create_llm(selected_provider, model_name=runtime.get("model"))
        else:
            llm = _create_llm(
                selected_provider,
                api_key=runtime.get("api_key"),
                model=runtime.get("model"),
                base_url=runtime.get("base_url"),
            )
        answer = await llm.generate(prompt, documents, temperature=0.1, max_tokens=int(max_tokens))
        return self._validate_model_candidates(answer, items, existing, int(limit))

    async def _approved_items(self, tenant_id: UUID, workspace_id: UUID, limit: int) -> list[KnowledgeItem]:
        result = await self.session.execute(select(KnowledgeItem).where(
            KnowledgeItem.tenant_id == str(tenant_id), KnowledgeItem.workspace_id == str(workspace_id),
            KnowledgeItem.deleted_at.is_(None), KnowledgeItem.review_status == "approved",
        ).order_by(KnowledgeItem.created_at.asc()).limit(limit))
        return list(result.scalars().all())

    async def _existing_edges(self, tenant_id: UUID, workspace_id: UUID) -> set[tuple[str, str]]:
        result = await self.session.execute(select(KnowledgeRelation.source_item_id, KnowledgeRelation.target_item_id).where(
            KnowledgeRelation.tenant_id == str(tenant_id), KnowledgeRelation.workspace_id == str(workspace_id),
        ))
        return {(str(row[0]), str(row[1])) for row in result.all()}

    @staticmethod
    def _item_text(item: KnowledgeItem) -> str:
        return "\n".join([f"标题：{item.title}", f"定义：{item.definition}", f"详情：{item.details or ''}", "结论：" + "；".join(item.conclusions or [])])

    @staticmethod
    def _model_prompt(items: list[KnowledgeItem], limit: int) -> str:
        catalog = "\n".join(f"- {item.id} | {item.title}" for item in items)
        return (
            "你是知识图谱关系候选分析器。只根据提供的已审核知识卡片提出可能存在的关系，"
            "不要创建事实，不要输出卡片目录之外的 ID。只返回 JSON 数组，不要 Markdown 或解释。"
            f"每项字段为 source_item_id、target_item_id、relation_type、description、score，最多 {limit} 项。"
            "relation_type 使用简短英文或 lower_snake_case，score 为 0 到 1 的数字。\n知识卡片目录：\n" + catalog
        )

    @staticmethod
    def _validate_model_candidates(answer: str, items: list[KnowledgeItem], existing: set[tuple[str, str]], limit: int) -> list[dict[str, Any]]:
        payload = KnowledgeRelationService._decode_model_payload(answer)
        item_map = {str(item.id): item for item in items}
        candidates: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for raw in payload:
            candidate = KnowledgeRelationService._candidate_from_model_item(raw, item_map, existing, seen)
            if candidate is not None:
                candidates.append(candidate)
        return sorted(candidates, key=lambda item: (-item["score"], str(item["source_item_id"])))[:limit]

    @staticmethod
    def _decode_model_payload(answer: str) -> list[dict[str, Any]]:
        match = re.search(r"\[[\s\S]*\]", answer or "")
        if not match:
            return []
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []

    @staticmethod
    def _candidate_from_model_item(raw: dict[str, Any], item_map: dict[str, KnowledgeItem], existing: set[tuple[str, str]], seen: set[tuple[str, str, str]]) -> dict[str, Any] | None:
        source_id, target_id = str(raw.get("source_item_id", "")), str(raw.get("target_item_id", ""))
        relation_type = str(raw.get("relation_type", "related")).strip().lower()[:64]
        if source_id not in item_map or target_id not in item_map or source_id == target_id or not relation_type:
            return None
        if (source_id, target_id) in existing or (target_id, source_id) in existing:
            return None
        key = (source_id, target_id, relation_type)
        if key in seen:
            return None
        seen.add(key)
        try:
            score = max(0.0, min(1.0, float(raw.get("score", 0.5))))
        except (TypeError, ValueError):
            score = 0.5
        source, target = item_map[source_id], item_map[target_id]
        return {
            "source_item_id": source.id, "target_item_id": target.id,
            "source_title": source.title, "target_title": target.title,
            "relation_type": relation_type, "score": round(score, 4), "matched_terms": [],
            "description": str(raw.get("description", ""))[:2000], "requires_human_review": True,
            "origin": "model",
        }

    @staticmethod
    def _terms(item: KnowledgeItem) -> set[str]:
        values = [item.title, item.definition, item.details or ""]
        values.extend(str(value) for value in (item.conclusions or []))
        if isinstance(item.extra_metadata, dict):
            values.extend(str(value) for value in (item.extra_metadata.get("tags") or []))
        text = " ".join(values).lower()
        terms = set(re.findall(r"[a-z][a-z0-9_-]{2,24}", text))
        for segment in re.findall(r"[\u4e00-\u9fff]{2,}", text):
            terms.add(segment)
            for size in (4, 3):
                terms.update(segment[index:index + size] for index in range(len(segment) - size + 1))
        title = str(item.title or "").strip().lower()
        if title:
            terms.add(title)
        return terms

    async def delete(
        self, *, relation_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, workspace_id: UUID,
    ) -> bool:
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)
        result = await self.session.execute(
            delete(KnowledgeRelation).where(
                KnowledgeRelation.id == str(relation_id), KnowledgeRelation.tenant_id == str(tenant_id),
                KnowledgeRelation.workspace_id == str(workspace_id),
            )
        )
        return bool(result.rowcount)

    async def _load_items(self, tenant_id: UUID, workspace_id: UUID, ids: list[UUID]) -> list[KnowledgeItem]:
        result = await self.session.execute(
            select(KnowledgeItem).where(
                KnowledgeItem.id.in_([str(item_id) for item_id in ids]),
                KnowledgeItem.tenant_id == str(tenant_id), KnowledgeItem.workspace_id == str(workspace_id),
                KnowledgeItem.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def _relation_dict(self, relation: KnowledgeRelation, item_by_id: dict[str, KnowledgeItem] | None = None) -> dict[str, Any]:
        if item_by_id is None:
            items = await self._load_items(UUID(str(relation.tenant_id)), UUID(str(relation.workspace_id)), [UUID(str(relation.source_item_id)), UUID(str(relation.target_item_id))])
            item_by_id = {str(item.id): item for item in items}
        source = item_by_id[str(relation.source_item_id)]
        target = item_by_id[str(relation.target_item_id)]
        return {
            "id": relation.id, "workspace_id": relation.workspace_id,
            "source_item_id": relation.source_item_id, "target_item_id": relation.target_item_id,
            "source_title": source.title, "target_title": target.title,
            "relation_type": relation.relation_type, "description": relation.description,
            "created_by": relation.created_by, "created_at": relation.created_at,
        }
