"""
文档复制服务单元测试
"""

import asyncio
import pytest
from uuid import UUID, uuid4
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.database.models import Base, Tenant, User, Workspace, Dataset, Document
from services.impl.document_copy_service import DocumentCopyService
from services.impl.document_service import DocumentServiceImpl


class TestDocumentCopyService:
    """文档复制服务测试"""
    
    def setup_method(self):
        """设置测试环境"""
        # 创建内存数据库
        self.engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        self.AsyncSessionLocal = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        
    async def setup_database(self):
        """初始化数据库"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
    async def create_test_data(self, session):
        """创建测试数据"""
        # 创建租户
        tenant = Tenant(
            id=str(uuid4()),
            name="Test Tenant",
            contact_email="test@example.com",
            plan="free",
            status="active"
        )
        session.add(tenant)
        await session.commit()
        
        # 创建管理员用户
        user = User(
            id=str(uuid4()),
            tenant_id=tenant.id,
            username="admin",
            email="admin@example.com",
            hashed_password="test_password",
            is_active=True,
            is_superuser=True
        )
        session.add(user)
        await session.commit()
        
        # 创建系统模板工作空间（在系统租户下）
        system_tenant = Tenant(
            id=str(uuid4()),
            name="__system__",
            contact_email="system@internal",
            plan="enterprise",
            status="active",
            extra_metadata={"is_system": True}
        )
        session.add(system_tenant)
        await session.commit()

        template_workspace = Workspace(
            id=str(uuid4()),
            tenant_id=system_tenant.id,
            name="__system_template__",
            description="系统模板工作空间",
            extra_metadata={"is_system_template": True}
        )
        session.add(template_workspace)
        await session.commit()
        
        # 创建系统模板知识库
        template_dataset = Dataset(
            id=str(uuid4()),
            workspace_id=template_workspace.id,
            name="系统模板知识库",
            description="系统模板知识库",
            is_public=True,
            embedding_model="sentence-transformers/all-MiniLM-L6-v2"
        )
        session.add(template_dataset)
        await session.commit()
        
        # 创建测试文档
        test_file = Path("./test_document.txt")
        test_file.write_text("Test document content")
        
        document = Document(
            id=str(uuid4()),
            dataset_id=template_dataset.id,
            file_name="test_document.txt",
            file_type="txt",
            file_size=len("Test document content"),
            file_path=str(test_file),
            status="completed"
        )
        session.add(document)
        await session.commit()
        
        # 创建目标工作空间
        target_workspace = Workspace(
            id=str(uuid4()),
            tenant_id=tenant.id,
            name="目标工作空间",
            description="目标工作空间"
        )
        session.add(target_workspace)
        await session.commit()
        
        # 创建目标知识库
        target_dataset = Dataset(
            id=str(uuid4()),
            workspace_id=target_workspace.id,
            name="目标知识库",
            description="目标知识库",
            is_public=True,
            embedding_model="sentence-transformers/all-MiniLM-L6-v2"
        )
        session.add(target_dataset)
        await session.commit()
        
        return {
            "tenant": tenant,
            "user": user,
            "template_workspace": template_workspace,
            "template_dataset": template_dataset,
            "document": document,
            "target_workspace": target_workspace,
            "target_dataset": target_dataset,
            "test_file": test_file
        }
    
    @pytest.mark.asyncio
    async def test_get_system_template_workspace(self):
        """测试获取系统模板工作空间"""
        await self.setup_database()
        
        async with self.AsyncSessionLocal() as session:
            test_data = await self.create_test_data(session)
            
            # 测试获取系统模板工作空间
            copy_service = DocumentCopyService(session)
            template_ws = await copy_service.get_system_template_workspace()
            
            assert template_ws is not None
            assert template_ws.name == "__system_template__"
            assert template_ws.extra_metadata.get("is_system_template") is True
    
    @pytest.mark.asyncio
    async def test_get_template_documents(self):
        """测试获取模板文档"""
        await self.setup_database()
        
        async with self.AsyncSessionLocal() as session:
            test_data = await self.create_test_data(session)
            
            # 测试获取模板文档
            copy_service = DocumentCopyService(session)
            documents = await copy_service.get_template_documents(UUID(test_data["template_workspace"].id))
            
            assert len(documents) == 1
            assert documents[0].file_name == "test_document.txt"
    
    @pytest.mark.asyncio
    async def test_copy_document(self):
        """测试复制单个文档"""
        await self.setup_database()
        
        async with self.AsyncSessionLocal() as session:
            test_data = await self.create_test_data(session)
            
            # 测试复制文档
            copy_service = DocumentCopyService(session)
            new_doc = await copy_service.copy_document(
                source_doc_id=UUID(test_data["document"].id),
                target_workspace_id=UUID(test_data["target_workspace"].id),
                target_dataset_id=UUID(test_data["target_dataset"].id)
            )
            
            assert new_doc is not None
            assert new_doc["file_name"] == "test_document.txt"
            assert new_doc["file_type"] == "txt"
            
            # 验证新文件存在
            new_file_path = Path(new_doc["file_path"])
            assert new_file_path.exists()
    
    @pytest.mark.asyncio
    async def test_copy_template_documents(self):
        """测试从模板复制文档"""
        await self.setup_database()
        
        async with self.AsyncSessionLocal() as session:
            test_data = await self.create_test_data(session)
            
            # 测试复制模板文档
            copy_service = DocumentCopyService(session)
            copied_docs = await copy_service.copy_template_documents(
                target_workspace_id=UUID(test_data["target_workspace"].id),
                target_dataset_id=UUID(test_data["target_dataset"].id)
            )
            
            assert len(copied_docs) == 1
            assert copied_docs[0]["file_name"] == "test_document.txt"
    
    def teardown_method(self):
        """清理测试环境"""
        # 删除测试文件
        test_file = Path("./test_document.txt")
        if test_file.exists():
            test_file.unlink()
        
        # 清理上传文件
        upload_dir = Path("./uploads")
        if upload_dir.exists():
            for file in upload_dir.iterdir():
                if file.is_file():
                    file.unlink()
            try:
                upload_dir.rmdir()
            except OSError:
                pass  # 忽略 Docker 挂载卷的删除失败


if __name__ == "__main__":
    test = TestDocumentCopyService()
    test.setup_method()
    asyncio.run(test.test_get_system_template_workspace())
    asyncio.run(test.test_get_template_documents())
    asyncio.run(test.test_copy_document())
    asyncio.run(test.test_copy_template_documents())
    test.teardown_method()
    print("All tests passed!")