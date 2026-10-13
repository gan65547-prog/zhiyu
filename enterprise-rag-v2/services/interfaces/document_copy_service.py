"""
文档复制服务接口
"""

from typing import Optional, Dict, Any, List
from uuid import UUID


class DocumentCopyService:
    """文档复制服务接口"""
    
    async def get_system_template_workspace(self) -> Optional[Any]:
        """获取系统模板工作空间
        
        Returns:
            Workspace: 系统模板工作空间
        """
        pass
    
    async def get_template_documents(self, workspace_id: UUID) -> List[Any]:
        """获取模板文档
        
        Args:
            workspace_id: 工作空间ID
            
        Returns:
            List[Document]: 文档列表
        """
        pass
    
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
        pass
    
    async def copy_template_documents(
        self, 
        target_workspace_id: UUID, 
        target_dataset_id: UUID
    ) -> List[Dict[str, Any]]:
        """从系统模板复制文档到目标知识库
        
        Args:
            target_workspace_id: 目标工作空间ID
            target_dataset_id: 目标数据集ID
            
        Returns:
            List[Dict[str, Any]]: 复制的文档列表
        """
        pass