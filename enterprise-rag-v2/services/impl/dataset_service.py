"""
数据集服务实现
"""

from typing import Optional, Dict, Any, Union
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from infrastructure.database.models import Dataset, Document, Workspace
from infrastructure.repositories.dataset_repository import DatasetRepositoryImpl
from services.interfaces.dataset_service import DatasetService
from core.value_objects.pagination import Pagination, Page


class DatasetServiceImpl(DatasetService):
    """数据集服务实现"""

    def __init__(self, session: AsyncSession):
        self._session = session
        self.dataset_repo = DatasetRepositoryImpl(session)

    @property
    def session(self) -> AsyncSession:
        """获取数据库会话"""
        return self._session

    async def verify_dataset_access(
        self,
        dataset_id: UUID,
        user_id: str,
        tenant_id: str,
        action: str = "read",
    ) -> None:
        """验证用户是否有权访问该数据集

        Args:
            dataset_id: 数据集ID
            user_id: 用户ID
            tenant_id: 租户ID
            action: "read" 或 "write"。公开数据集允许任何人 read，但拒绝非成员 write。
        """
        from infrastructure.database.models import Dataset, Workspace, WorkspaceMember
        from sqlalchemy import select

        # 1. 获取数据集和其所属的workspace
        result = await self.session.execute(
            select(Dataset, Workspace)
            .join(Workspace, Dataset.workspace_id == Workspace.id)
            .where(Dataset.id == str(dataset_id))
        )
        row = result.first()

        if not row:
            raise ValueError(f"数据集 {dataset_id} 不存在")

        dataset, workspace = row

        # 2. 公共数据集：读取允许所有人，写入需工作空间成员
        if getattr(dataset, 'is_public', False):
            if action == "read":
                return
            # write — 继续走成员检查

        # 3. 验证workspace属于用户的租户
        if workspace.tenant_id != tenant_id:
            raise PermissionError(f"您无权访问该数据集（跨租户访问被拒绝）")

        # 3.5 公共工作空间：同租户内所有用户自动可读，跳过成员检查
        workspace_meta = workspace.extra_metadata or {}
        if workspace_meta.get("is_public_workspace") is True:
            return

        # 4. 验证用户是该workspace的成员
        member_result = await self.session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.user_id == user_id
            )
        )
        member = member_result.scalar_one_or_none()

        if not member:
            raise PermissionError(f"您不是该工作空间的成员，无权访问该数据集")

    async def create_dataset(
        self,
        workspace_id: UUID,
        name: str,
        description: Optional[str] = None,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        is_public: bool = False
    ) -> dict:
        """创建数据集
        
        Args:
            workspace_id: 工作空间ID
            name: 数据集名称
            description: 数据集描述
            embedding_model: 嵌入模型
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
            metadata: 元数据
            user_id: 用户ID（用于权限验证）
            tenant_id: 租户ID（用于权限验证）
            is_public: 是否为公共知识库
        """
        # 如果提供了user_id和tenant_id，验证权限
        if user_id and tenant_id:
            from infrastructure.database.models import Workspace, WorkspaceMember
            from sqlalchemy import select
            
            # 验证workspace存在且属于该租户
            workspace_result = await self.session.execute(
                select(Workspace).where(Workspace.id == str(workspace_id))
            )
            workspace = workspace_result.scalar_one_or_none()
            
            if not workspace:
                raise ValueError(f"工作空间 {workspace_id} 不存在")
            
            if workspace.tenant_id != tenant_id:
                raise PermissionError(f"您无权在该工作空间创建数据集（跨租户访问被拒绝）")
            
            # 验证用户是该workspace的成员
            member_result = await self.session.execute(
                select(WorkspaceMember)
                .where(
                    WorkspaceMember.workspace_id == str(workspace_id),
                    WorkspaceMember.user_id == user_id
                )
            )
            member = member_result.scalar_one_or_none()
            
            if not member:
                raise PermissionError(f"您不是该工作空间的成员，无权创建数据集")
        
        dataset = Dataset(
            workspace_id=str(workspace_id),
            name=name,
            description=description,
            is_public=is_public,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            extra_metadata=metadata or {}
        )

        created = await self.dataset_repo.create(dataset)

        return {
            "id": str(created.id),
            "workspace_id": str(created.workspace_id),
            "name": created.name,
            "description": created.description,
            "embedding_model": created.embedding_model,
            "chunk_size": created.chunk_size,
            "chunk_overlap": created.chunk_overlap,
            "metadata": created.extra_metadata,
            "is_public": created.is_public,
            "created_at": created.created_at.isoformat() if created.created_at else None
        }

    async def get_dataset(self, dataset_id: UUID) -> Optional[dict]:
        """获取数据集详情"""
        # 将UUID转换为字符串格式（数据库中存储的是字符串）
        dataset_id_str = str(dataset_id) if hasattr(dataset_id, 'hex') else dataset_id
        dataset = await self.dataset_repo.get_by_id(dataset_id_str)
        if not dataset:
            return None

        # 计算文档统计信息
        from infrastructure.database.models import Document, DocumentStatus
        
        # 总文档数
        total_result = await self.session.execute(
            select(func.count()).select_from(Document).where(Document.dataset_id == dataset_id_str)
        )
        total_documents = total_result.scalar_one()
        
        # 已索引文档数（完成状态）
        completed_result = await self.session.execute(
            select(func.count()).select_from(Document).where(
                Document.dataset_id == dataset_id_str,
                Document.status == DocumentStatus.COMPLETED
            )
        )
        indexed_documents = completed_result.scalar_one()
        
        # 处理中文档数
        processing_result = await self.session.execute(
            select(func.count()).select_from(Document).where(
                Document.dataset_id == dataset_id_str,
                Document.status == DocumentStatus.PROCESSING
            )
        )
        pending_documents = processing_result.scalar_one()
        
        # 失败文档数
        failed_result = await self.session.execute(
            select(func.count()).select_from(Document).where(
                Document.dataset_id == dataset_id_str,
                Document.status == DocumentStatus.FAILED
            )
        )
        failed_documents = failed_result.scalar_one()

        return {
            "id": str(dataset.id),
            "workspace_id": str(dataset.workspace_id),
            "name": dataset.name,
            "description": dataset.description,
            "embedding_model": dataset.embedding_model,
            "chunk_size": dataset.chunk_size,
            "chunk_overlap": dataset.chunk_overlap,
            "metadata": dataset.extra_metadata if hasattr(dataset, 'extra_metadata') else {},
            "config": {
                "embedding_model": dataset.embedding_model,
                "chunk_size": dataset.chunk_size,
                "chunk_overlap": dataset.chunk_overlap,
                "retrieval_model": "semantic"
            },
            "document_count": total_documents,
            "statistics": {
                "total_documents": total_documents,
                "indexed_documents": indexed_documents,
                "pending_documents": pending_documents,
                "failed_documents": failed_documents
            },
            "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
            "updated_at": dataset.updated_at.isoformat() if dataset.updated_at else None
        }

    async def update_dataset(
        self,
        dataset_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        """更新数据集"""
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise ValueError("数据集不存在")

        if name is not None:
            dataset.name = name
        if description is not None:
            dataset.description = description
        if metadata is not None:
            dataset.extra_metadata = metadata

        updated = await self.dataset_repo.update(dataset)

        return {
            "id": str(updated.id),
            "workspace_id": str(updated.workspace_id),
            "name": updated.name,
            "description": updated.description,
            "embedding_model": updated.embedding_model,
            "chunk_size": updated.chunk_size,
            "chunk_overlap": updated.chunk_overlap,
            "metadata": updated.extra_metadata if hasattr(updated, 'extra_metadata') else updated.metadata,
            "is_public": updated.is_public,
            "created_at": updated.created_at.isoformat() if updated.created_at else None,
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None
        }

    async def delete_dataset(self, dataset_id: UUID) -> bool:
        """删除数据集"""
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            return False

        await self.dataset_repo.delete(dataset_id)
        return True

    async def list_datasets(
        self,
        workspace_id: Union[UUID, str],
        keyword: Optional[str] = None,
        pagination: Optional[Pagination] = None,
        include_public: bool = False,
        tenant_id: Optional[str] = None,
    ) -> Page:
        """查询数据集列表

        include_public=True 时，同时返回同一租户下其他 workspace 的公开数据集。
        """
        workspace_id_str = str(workspace_id) if hasattr(workspace_id, 'hex') else workspace_id
        filters = {"workspace_id": workspace_id_str}
        result = await self.dataset_repo.list(filters, pagination)

        # 列表页、工作台总览和书架都会直接消费 document_count。
        # 旧实现只返回 Dataset 自身字段，导致详情页有文档而列表页显示 0，
        # 进一步让首页把已建立的知识库误判成“待建立”。一次聚合查询补齐
        # 当前页的统计，避免对每个知识库逐条查询。
        dataset_ids = [str(ds.id) for ds in result.items]
        document_counts: dict[str, int] = {}
        if dataset_ids:
            document_count_result = await self.session.execute(
                select(Document.dataset_id, func.count(Document.id))
                .where(Document.dataset_id.in_(dataset_ids))
                .group_by(Document.dataset_id)
            )
            document_counts = {
                str(dataset_id): int(count or 0)
                for dataset_id, count in document_count_result.all()
            }

        items = []
        seen_ids = set()
        for ds in result.items:
            seen_ids.add(str(ds.id))
            items.append(self._ds_to_dict(ds, document_count=document_counts.get(str(ds.id), 0)))

        # 追加同租户内其它工作空间的公开数据集。默认列表不追加，避免切换
        # workspace 后把旧工作空间知识库显示到当前页面。
        if include_public:
            conditions = [
                Dataset.is_public == True,
                Dataset.workspace_id != workspace_id_str,
            ]
            if tenant_id:
                conditions.append(Workspace.tenant_id == str(tenant_id))
            public_result = await self.session.execute(
                select(Dataset)
                .join(Workspace, Dataset.workspace_id == Workspace.id)
                .where(*conditions)
            )
            public_datasets = public_result.scalars().all()
            public_ids = [str(ds.id) for ds in public_datasets]
            if public_ids:
                public_count_result = await self.session.execute(
                    select(Document.dataset_id, func.count(Document.id))
                    .where(Document.dataset_id.in_(public_ids))
                    .group_by(Document.dataset_id)
                )
                document_counts.update({
                    str(dataset_id): int(count or 0)
                    for dataset_id, count in public_count_result.all()
                })
            for ds in public_datasets:
                if str(ds.id) not in seen_ids:
                    seen_ids.add(str(ds.id))
                    items.append(self._ds_to_dict(ds, document_count=document_counts.get(str(ds.id), 0)))

        return Page(
            items=items,
            total=len(items) if include_public else result.total,
            page=pagination.page if pagination else 1,
            page_size=pagination.page_size if pagination else len(items)
        )

    @staticmethod
    def _ds_to_dict(ds, document_count: int = 0) -> dict:
        return {
            "id": str(ds.id),
            "workspace_id": str(ds.workspace_id),
            "name": ds.name,
            "description": ds.description,
            "embedding_model": ds.embedding_model,
            "chunk_size": ds.chunk_size,
            "chunk_overlap": ds.chunk_overlap,
            "document_count": document_count,
            "metadata": ds.extra_metadata if hasattr(ds, 'extra_metadata') else {},
            "created_at": ds.created_at.isoformat() if ds.created_at else None,
        }

    async def get_dataset_statistics(self, dataset_id: UUID) -> dict:
        """获取数据集统计信息"""
        dataset = await self.dataset_repo.get_by_id(dataset_id)
        if not dataset:
            raise ValueError("数据集不存在")

        doc_result = await self.session.execute(
            select(func.count()).select_from(Document).where(Document.dataset_id == dataset_id)
        )
        document_count = doc_result.scalar_one()

        return {
            "dataset_id": str(dataset_id),
            "document_count": document_count,
            "chunk_size": dataset.chunk_size,
            "chunk_overlap": dataset.chunk_overlap
        }
