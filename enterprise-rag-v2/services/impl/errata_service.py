"""
勘误服务实现
"""

from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy import Text, select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import DocumentErrata, ErrataSeverity, ErrataStatus
from infrastructure.database.session import get_db_context
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class ErrataService:
    """勘误管理服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_errata(
        self,
        errata_code: str,
        title: str,
        description: str,
        severity: str = "minor",
        fix_suggestion: Optional[str] = None,
        source_evidence: Optional[str] = None,
        affected_document_ids: Optional[List[str]] = None,
        related_document_ids: Optional[List[str]] = None,
        reported_by: Optional[str] = None,
    ) -> DocumentErrata:
        """创建勘误"""
        # 检查编号唯一性
        existing = await self.session.execute(
            select(DocumentErrata).where(DocumentErrata.errata_code == errata_code)
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"勘误编号 '{errata_code}' 已存在")

        sev = self._normalize_severity(severity)

        errata = DocumentErrata(
            errata_code=errata_code,
            title=title,
            description=description,
            severity=sev,
            status=ErrataStatus.OPEN,
            fix_suggestion=fix_suggestion,
            source_evidence=source_evidence,
            affected_document_ids=affected_document_ids or [],
            related_document_ids=related_document_ids or [],
            reported_by=reported_by,
        )
        self.session.add(errata)
        await self.session.commit()
        await self.session.refresh(errata)
        logger.info(f"Created errata {errata_code}: {title}")
        return errata

    async def get_errata(self, errata_id: UUID) -> Optional[DocumentErrata]:
        """获取单条勘误"""
        result = await self.session.execute(
            select(DocumentErrata).where(DocumentErrata.id == str(errata_id))
        )
        return result.scalar_one_or_none()

    async def list_errata(
        self,
        severity: Optional[str] = None,
        status_filter: Optional[str] = None,
        document_id: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """查询勘误列表"""
        query = select(DocumentErrata)
        count_q = select(func.count()).select_from(DocumentErrata)

        if severity:
            sev_enum = self._normalize_severity(severity)
            query = query.where(DocumentErrata.severity == sev_enum)
            count_q = count_q.where(DocumentErrata.severity == sev_enum)

        if status_filter:
            try:
                st_enum = ErrataStatus(status_filter)
                query = query.where(DocumentErrata.status == st_enum)
                count_q = count_q.where(DocumentErrata.status == st_enum)
            except ValueError:
                pass

        if document_id:
            # 检查 affected_document_ids JSON 数组是否包含该 ID
            # SQLite: use LIKE; PostgreSQL: use JSONB contains
            query = query.where(
                DocumentErrata.affected_document_ids.cast(Text).contains(document_id)
            )
            count_q = count_q.where(
                DocumentErrata.affected_document_ids.cast(Text).contains(document_id)
            )

        if keyword:
            like_pat = f"%{keyword}%"
            query = query.where(
                or_(
                    DocumentErrata.title.ilike(like_pat),
                    DocumentErrata.description.ilike(like_pat),
                    DocumentErrata.errata_code.ilike(like_pat),
                )
            )
            count_q = count_q.where(
                or_(
                    DocumentErrata.title.ilike(like_pat),
                    DocumentErrata.description.ilike(like_pat),
                    DocumentErrata.errata_code.ilike(like_pat),
                )
            )

        # 总数
        total_result = await self.session.execute(count_q)
        total = total_result.scalar_one()

        # 分页
        offset = (page - 1) * page_size
        query = query.order_by(DocumentErrata.created_at.desc()).offset(offset).limit(page_size)
        result = await self.session.execute(query)
        items = result.scalars().all()

        return {"items": list(items), "total": total}

    async def update_errata(self, errata_id: UUID, **kwargs) -> Optional[DocumentErrata]:
        """更新勘误"""
        errata = await self.get_errata(errata_id)
        if not errata:
            return None

        if "severity" in kwargs and kwargs["severity"] is not None:
            kwargs["severity"] = self._normalize_severity(kwargs["severity"])
        if "status" in kwargs and kwargs["status"] is not None:
            try:
                kwargs["status"] = ErrataStatus(kwargs["status"])
            except ValueError:
                pass

        # 检查状态变更
        new_status = kwargs.get("status")
        if new_status and new_status in (ErrataStatus.RESOLVED, ErrataStatus.CLOSED):
            if not errata.resolved_at:
                from datetime import datetime as _dt
                kwargs["resolved_at"] = _dt.utcnow()

        for key, value in kwargs.items():
            if value is not None and hasattr(errata, key):
                setattr(errata, key, value)

        await self.session.commit()
        await self.session.refresh(errata)
        return errata

    async def delete_errata(self, errata_id: UUID) -> bool:
        """删除勘误"""
        errata = await self.get_errata(errata_id)
        if not errata:
            return False
        await self.session.delete(errata)
        await self.session.commit()
        return True

    async def get_errata_for_document(self, document_id: str) -> List[DocumentErrata]:
        """获取与指定文档关联的所有勘误"""
        result = await self.session.execute(
            select(DocumentErrata).where(
                DocumentErrata.affected_document_ids.cast(Text).contains(document_id)
            )
        )
        return list(result.scalars().all())

    async def get_active_errata_for_documents(
        self, document_ids: List[str]
    ) -> Dict[str, List[dict]]:
        """批量查询文档的活跃勘误 — 供 RAG 检索管道使用

        Returns: {doc_id: [errata_summary, ...]}
        """
        if not document_ids:
            return {}

        # 获取所有未关闭的勘误
        result = await self.session.execute(
            select(DocumentErrata).where(
                DocumentErrata.status.in_([ErrataStatus.OPEN, ErrataStatus.IN_PROGRESS])
            )
        )
        all_active = result.scalars().all()

        doc_errata_map: Dict[str, List[dict]] = {did: [] for did in document_ids}
        for errata in all_active:
            for affected_id in (errata.affected_document_ids or []):
                if affected_id in doc_errata_map:
                    doc_errata_map[affected_id].append({
                        "errata_code": errata.errata_code,
                        "title": errata.title,
                        "severity": errata.severity.value if hasattr(errata.severity, 'value') else errata.severity,
                        "fix_suggestion": errata.fix_suggestion,
                    })

        return doc_errata_map

    @staticmethod
    def _normalize_severity(severity: str) -> ErrataSeverity:
        sev_lower = severity.lower().strip()
        mapping = {
            "critical": ErrataSeverity.CRITICAL,
            "major": ErrataSeverity.MAJOR,
            "minor": ErrataSeverity.MINOR,
            "note": ErrataSeverity.NOTE,
        }
        if sev_lower not in mapping:
            raise ValueError(f"无效的严重程度: '{severity}'，可选: critical/major/minor/note")
        return mapping[sev_lower]


async def get_errata_service() -> ErrataService:
    """依赖注入工厂"""
    async with get_db_context() as session:
        yield ErrataService(session)
