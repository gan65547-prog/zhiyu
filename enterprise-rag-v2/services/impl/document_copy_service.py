"""
文档复制服务实现

提供从系统模板复制文档到租户公共知识库的功能
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.config import get_settings
from infrastructure.database.models import Document, Dataset, Workspace, Tenant
from infrastructure.repositories.document_repository import DocumentRepositoryImpl
from infrastructure.repositories.dataset_repository import DatasetRepositoryImpl
from infrastructure.repositories.workspace_repository import WorkspaceRepositoryImpl
from services.interfaces.document_service import DocumentService
from services.impl.document_service import DocumentServiceImpl
from infrastructure.logging.logger import get_logger

settings = get_settings()

logger = get_logger("services.impl.document_copy_service")


class DocumentCopyService:
    """文档复制服务"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.document_repo = DocumentRepositoryImpl(session)
        self.dataset_repo = DatasetRepositoryImpl(session)
        self.workspace_repo = WorkspaceRepositoryImpl(session)
        self.document_service = DocumentServiceImpl(session)
        from services.impl.workspace_service import WorkspaceServiceImpl
        self.workspace_service = WorkspaceServiceImpl(session)
    
    async def get_system_template_workspace(self, user_id: Optional[UUID] = None) -> Optional[Workspace]:
        """获取系统模板工作空间

        Args:
            user_id: 用户ID，用于权限验证（可选）

        Returns:
            Workspace: 系统模板工作空间
        """
        result = await self.session.execute(
            select(Workspace).where(
                Workspace.name == "__system_template__",
                Workspace.extra_metadata.contains({"is_system_template": True})
            )
        )
        workspace = result.scalar_one_or_none()
        
        # 如果提供了用户ID，验证访问权限
        if workspace and user_id:
            await self.workspace_service.verify_system_template_access(workspace.id, user_id)
        
        return workspace

    async def get_system_tenant(self):
        """获取系统租户

        Returns:
            Tenant: 系统租户
        """
        result = await self.session.execute(
            select(Tenant).where(Tenant.name == "__system__")
        )
        return result.scalar_one_or_none()
    
    async def get_template_documents(self, workspace_id: UUID) -> List[Document]:
        """获取模板文档
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            List[Document]: 文档列表
        """
        # 获取工作空间下的所有数据集
        result = await self.session.execute(
            select(Dataset).where(Dataset.workspace_id == str(workspace_id))
        )
        datasets = result.scalars().all()
        
        if not datasets:
            return []
        
        # 获取所有数据集下的文档
        dataset_ids = [str(ds.id) for ds in datasets]
        result = await self.session.execute(
            select(Document).where(Document.dataset_id.in_(dataset_ids))
        )
        return result.scalars().all()
    
    async def _copy_file(self, source_file_path: str) -> str:
        """复制文件到新位置
        
        Args:
            source_file_path: 源文件路径
            
        Returns:
            str: 新文件路径
        """
        import shutil
        import uuid
        
        source_path = Path(source_file_path)
        if not source_path.exists():
            raise FileNotFoundError(f"源文件不存在: {source_file_path}")
        
        # 创建目标目录
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成新文件名
        file_ext = source_path.suffix
        new_filename = f"{uuid.uuid4()}{file_ext}"
        target_path = upload_dir / new_filename
        
        # 复制文件
        shutil.copy2(source_path, target_path)
        
        return str(target_path)
    
    async def copy_document(
        self, 
        source_doc_id: UUID, 
        target_workspace_id: UUID, 
        target_dataset_id: UUID
    ) -> Dict[str, Any]:
        """复制单个文档
        
        Args:
            source_doc_id: 源文档ID
            target_workspace_id: 目标工作空间ID
            target_dataset_id: 目标数据集ID
            
        Returns:
            Dict[str, Any]: 新文档信息
        """
        # 获取源文档信息
        source_doc = await self.document_service.get_document(source_doc_id)
        if not source_doc:
            raise ValueError(f"源文档不存在: {source_doc_id}")
        
        try:
            # 复制文件到新位置
            new_file_path = await self._copy_file(source_doc["file_path"])
            
            # 创建新文档记录
            new_doc = await self.document_service.upload_document(
                dataset_id=target_dataset_id,
                file_path=new_file_path,
                file_name=source_doc["file_name"],
                file_type=source_doc["file_type"],
                file_size=source_doc["file_size"],
                tags=source_doc.get("tags", []),
                metadata=source_doc.get("metadata", {})
            )
            
            # 重新处理文档（向量化）
            await self.document_service.process_document(new_doc["id"])
            
            logger.info(f"文档复制成功: {source_doc['file_name']} -> {new_doc['id']}")
            return new_doc
        except Exception as e:
            logger.error(f"文档复制失败: {e}", exc_info=True)
            raise
    
    async def copy_template_documents(
        self, 
        target_workspace_id: UUID, 
        target_dataset_id: UUID,
        user_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """从系统模板复制文档到目标知识库
        
        Args:
            target_workspace_id: 目标工作空间ID
            target_dataset_id: 目标数据集ID
            user_id: 用户ID，用于权限验证（可选）
            
        Returns:
            List[Dict[str, Any]]: 复制的文档列表
        """
        # 获取系统模板工作空间
        template_ws = await self.get_system_template_workspace(user_id)
        if not template_ws:
            logger.warning("系统模板工作空间不存在，跳过文档复制")
            return []
        
        # 获取模板文档
        template_docs = await self.get_template_documents(template_ws.id)
        if not template_docs:
            logger.info("模板工作空间中无文档，跳过复制")
            return []
        
        # 复制每个文档
        copied_docs = []
        for doc in template_docs:
            try:
                new_doc = await self.copy_document(
                    source_doc_id=UUID(doc.id),
                    target_workspace_id=target_workspace_id,
                    target_dataset_id=target_dataset_id
                )
                copied_docs.append(new_doc)
            except Exception as e:
                logger.error(f"复制文档失败 {doc.file_name}: {e}")
                continue
        
        logger.info(f"成功复制 {len(copied_docs)} 个文档到租户公共知识库")
        return copied_docs