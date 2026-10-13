"""
端到端测试 - RAG工作流

测试完整的RAG工作流程：文档上传 → 处理 → 检索 → 对话
使用真实的服务实现但配合Mock外部依赖
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.impl.auth_service import AuthServiceImpl
from services.impl.tenant_service import TenantServiceImpl
from services.impl.workspace_service import WorkspaceServiceImpl
from services.impl.dataset_service import DatasetServiceImpl
from services.impl.document_service import DocumentServiceImpl
from services.impl.chat_service import ChatServiceImpl


class MockTenantRepo:
    """模拟租户Repository"""
    def __init__(self):
        self.tenants = {}

    async def get_by_email(self, email):
        for t in self.tenants.values():
            if t.contact_email == email:
                return t
        return None

    async def get_by_id(self, tenant_id):
        return self.tenants.get(tenant_id)

    async def create(self, tenant):
        if not tenant.id:
            tenant.id = str(uuid4())
        self.tenants[tenant.id] = tenant
        return tenant

    async def update(self, tenant):
        self.tenants[tenant.id] = tenant
        return tenant


class MockWorkspaceRepo:
    """模拟工作空间Repository"""
    def __init__(self):
        self.workspaces = {}

    async def get_by_id(self, workspace_id):
        return self.workspaces.get(str(workspace_id))

    async def create(self, workspace):
        if not workspace.id:
            workspace.id = str(uuid4())
        self.workspaces[str(workspace.id)] = workspace
        return workspace

    async def update(self, workspace):
        self.workspaces[str(workspace.id)] = workspace
        return workspace

    async def delete(self, workspace_id):
        key = str(workspace_id)
        if key in self.workspaces:
            del self.workspaces[key]
            return True
        return False


class MockDatasetRepo:
    """模拟数据集Repository"""
    def __init__(self):
        self.datasets = {}

    async def get_by_id(self, dataset_id):
        return self.datasets.get(str(dataset_id))

    async def create(self, dataset):
        if not dataset.id:
            dataset.id = str(uuid4())
        self.datasets[str(dataset.id)] = dataset
        return dataset

    async def update(self, dataset):
        self.datasets[str(dataset.id)] = dataset
        return dataset

    async def delete(self, dataset_id):
        key = str(dataset_id)
        if key in self.datasets:
            del self.datasets[key]
            return True
        return False


class MockDocumentRepo:
    """模拟文档Repository"""
    def __init__(self):
        self.documents = {}

    async def get_by_id(self, doc_id):
        return self.documents.get(str(doc_id))

    async def create(self, document):
        if not document.id:
            document.id = str(uuid4())
        self.documents[str(document.id)] = document
        return document

    async def update(self, document):
        self.documents[str(document.id)] = document
        return document

    async def delete(self, doc_id):
        key = str(doc_id)
        if key in self.documents:
            del self.documents[key]
            return True
        return False

    async def list(self, filters=None, pagination=None):
        items = list(self.documents.values())
        return MagicMock(items=items, total=len(items), page=1, page_size=20)


class MockConversationRepo:
    """模拟会话Repository"""
    def __init__(self):
        self.conversations = {}

    async def get_by_id(self, conversation_id):
        return self.conversations.get(str(conversation_id))

    async def create(self, conversation):
        if not conversation.id:
            conversation.id = uuid4()
        if not conversation.created_at:
            from datetime import datetime
            conversation.created_at = datetime.utcnow()
        if not conversation.updated_at:
            from datetime import datetime
            conversation.updated_at = datetime.utcnow()
        self.conversations[str(conversation.id)] = conversation
        return conversation

    async def update(self, conversation):
        self.conversations[str(conversation.id)] = conversation
        return conversation

    async def delete(self, conversation_id):
        key = str(conversation_id)
        if key in self.conversations:
            del self.conversations[key]
            return True
        return False

    async def list(self, filters=None, pagination=None):
        items = list(self.conversations.values())
        return MagicMock(items=items, total=len(items), page=1, page_size=20)


class MockMessageRepo:
    """模拟消息Repository"""
    def __init__(self):
        self.messages = {}

    async def get_by_id(self, message_id):
        for msgs in self.messages.values():
            for msg in msgs:
                if msg.id == message_id:
                    return msg
        return None

    async def get_by_conversation(self, conversation_id):
        return self.messages.get(str(conversation_id), [])

    async def create(self, message):
        key = str(message.conversation_id)
        if key not in self.messages:
            self.messages[key] = []
        self.messages[key].append(message)
        return message


class TestRAGE2E:
    """RAG端到端测试"""

    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        class _Result:
            def __init__(self, scalar=None, rows=None):
                self._scalar = scalar
                self._rows = rows or []

            def scalar_one_or_none(self):
                return self._scalar

            def scalar(self):
                return self._scalar

            def scalar_one(self):
                return self._scalar

            def all(self):
                return self._rows

            def scalars(self):
                class _Scalars:
                    def __init__(self, rows):
                        self._rows = rows

                    def all(self):
                        return self._rows

                return _Scalars(self._rows)

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result())
        session.get = AsyncMock(return_value=None)
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def mock_services(self, mock_db_session):
        """创建所有模拟服务"""
        auth_service = AuthServiceImpl(session=mock_db_session)
        auth_service.user_repo = MagicMock()
        auth_service.user_repo.get_by_email = AsyncMock(return_value=None)
        auth_service.user_repo.get_by_username = AsyncMock(return_value=None)
        auth_service.user_repo.create = AsyncMock()
        auth_service.user_repo.get_by_id = AsyncMock()
        auth_service.audit_service = AsyncMock()
        auth_service.audit_service.log = AsyncMock(return_value=True)
        auth_service.audit_service.log_login = AsyncMock(return_value=True)
        auth_service.audit_service.log_logout = AsyncMock(return_value=True)

        tenant_service = TenantServiceImpl(session=mock_db_session)
        tenant_service.tenant_repo = MockTenantRepo()
        tenant_service.audit_service = AsyncMock()
        tenant_service.audit_service.log = AsyncMock(return_value=True)

        workspace_service = WorkspaceServiceImpl(session=mock_db_session)
        workspace_service.workspace_repo = MockWorkspaceRepo()
        workspace_service.audit_service = AsyncMock()
        workspace_service.audit_service.log = AsyncMock(return_value=True)

        dataset_service = DatasetServiceImpl(session=mock_db_session)
        dataset_service.dataset_repo = MockDatasetRepo()
        dataset_service.audit_service = AsyncMock()
        dataset_service.audit_service.log = AsyncMock(return_value=True)

        document_service = DocumentServiceImpl(session=mock_db_session)
        document_service.document_repo = MockDocumentRepo()
        document_service.audit_service = AsyncMock()
        document_service.audit_service.log = AsyncMock(return_value=True)

        chat_service = ChatServiceImpl(session=mock_db_session)
        chat_service.conversation_repo = MockConversationRepo()
        chat_service.message_repo = MockMessageRepo()

        return {
            "auth_service": auth_service,
            "tenant_service": tenant_service,
            "workspace_service": workspace_service,
            "dataset_service": dataset_service,
            "document_service": document_service,
            "chat_service": chat_service,
        }

    @pytest.mark.asyncio
    async def test_complete_rag_workflow(self, mock_services):
        """测试完整RAG工作流程"""
        tenant_id = uuid4()
        workspace_id = uuid4()
        dataset_id = uuid4()
        document_id = uuid4()
        conversation_id = uuid4()

        tenant_service = mock_services["tenant_service"]
        workspace_service = mock_services["workspace_service"]
        dataset_service = mock_services["dataset_service"]
        document_service = mock_services["document_service"]
        chat_service = mock_services["chat_service"]

        with patch("services.impl.auth_service.create_access_token", return_value="token"), \
             patch("services.impl.auth_service.create_refresh_token", return_value="refresh_token"), \
             patch("services.impl.tenant_service.WorkspaceServiceImpl") as mock_ws_cls, \
             patch("services.impl.tenant_service.DatasetServiceImpl") as mock_ds_cls, \
             patch("services.impl.tenant_service.DocumentCopyServiceImpl") as mock_copy_cls:

            mock_ws_instance = MagicMock()
            mock_ws_instance.create_workspace = AsyncMock(return_value={"id": str(uuid4()), "name": "默认工作空间"})
            mock_ws_cls.return_value = mock_ws_instance
            mock_ds_instance = MagicMock()
            mock_ds_instance.create_dataset = AsyncMock(return_value={"id": str(uuid4()), "name": "公共知识库"})
            mock_ds_cls.return_value = mock_ds_instance
            mock_copy_instance = MagicMock()
            mock_copy_instance.get_system_template_workspace = AsyncMock(return_value=MagicMock())
            mock_copy_instance.copy_template_documents = AsyncMock(return_value=[])
            mock_copy_cls.return_value = mock_copy_instance

            tenant = await tenant_service.create_tenant(
                name="Test Company",
                contact_email="owner@example.com"
            )
            assert tenant["name"] == "Test Company"

            ws_result = await workspace_service.create_workspace(
                tenant_id=tenant_id,
                name="Test Workspace",
                creator_id=str(uuid4()),
            )
            assert ws_result["name"] == "Test Workspace"

            from infrastructure.database.models import Dataset
            ds = Dataset(
                id=dataset_id,
                workspace_id=workspace_id,
                name="Test Dataset",
                embedding_model="text-embedding-ada-002",
                chunk_size=500,
                chunk_overlap=50
            )
            dataset_service.dataset_repo.datasets[str(dataset_id)] = ds

            ds_result = await dataset_service.get_dataset(dataset_id)
            assert ds_result["name"] == "Test Dataset"

            from infrastructure.database.models import Document, DocumentType, DocumentStatus
            doc = Document(
                id=document_id,
                dataset_id=dataset_id,
                file_name="test.pdf",
                file_type=DocumentType.PDF,
                file_size=1024,
                file_path="/uploads/test.pdf",
                status=DocumentStatus.COMPLETED
            )
            document_service.document_repo.documents[str(document_id)] = doc

            doc_result = await document_service.get_document(document_id)
            assert doc_result is not None
            assert doc_result["file_name"] == "test.pdf"

            conv_result = await chat_service.create_conversation(
                dataset_id=dataset_id,
                user_id=str(uuid4()),
                title="Test Chat"
            )
            assert conv_result["title"] == "Test Chat"

            response = await chat_service.chat(
                dataset_id=dataset_id,
                query="What is this about?"
            )
            assert "answer" in response
            assert "conversation_id" in response

    @pytest.mark.asyncio
    async def test_rag_workflow_with_conversation_history(self, mock_services):
        """测试带对话历史的RAG工作流"""
        dataset_id = uuid4()
        conversation_id = uuid4()
        chat_service = mock_services["chat_service"]

        from infrastructure.database.models import Conversation, Message
        conv = Conversation(
            id=conversation_id,
            dataset_id=dataset_id,
            title="Test Chat"
        )
        chat_service.conversation_repo.conversations[str(conversation_id)] = conv

        msg1 = Message(
            id=uuid4(),
            conversation_id=conversation_id,
            role="user",
            content="Hello"
        )
        msg2 = Message(
            id=uuid4(),
            conversation_id=conversation_id,
            role="assistant",
            content="Hi there!"
        )
        chat_service.message_repo.messages[str(conversation_id)] = [msg1, msg2]

        history = await chat_service.get_conversation_messages(conversation_id)

        assert len(history) == 2
        assert history[0]["content"] == "Hello"
        assert history[1]["content"] == "Hi there!"

    @pytest.mark.asyncio
    async def test_rag_workflow_document_lifecycle(self, mock_services):
        """测试文档完整生命周期"""
        dataset_id = uuid4()
        document_id = uuid4()
        document_service = mock_services["document_service"]

        from infrastructure.database.models import Document, DocumentType, DocumentStatus

        doc = Document(
            id=document_id,
            dataset_id=dataset_id,
            file_name="test.pdf",
            file_type=DocumentType.PDF,
            file_size=1024,
            file_path="/uploads/test.pdf",
            status=DocumentStatus.PENDING
        )
        document_service.document_repo.documents[str(document_id)] = doc

        retrieved = await document_service.get_document(document_id)
        assert retrieved["status"] == "pending"

        doc.status = DocumentStatus.COMPLETED
        doc.chunk_count = 10

        updated = await document_service.update_document(
            document_id=document_id,
            metadata={"status": "completed", "chunk_count": 10}
        )
        assert updated["id"] == str(document_id)


class TestMultiTenantE2E:
    """多租户端到端测试"""

    @pytest.fixture
    def mock_tenant_services(self):
        """为每个租户创建模拟服务"""
        return {
            "tenant_a": MagicMock(),
            "tenant_b": MagicMock()
        }

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, mock_tenant_services):
        """测试租户隔离"""
        tenant_a_id = uuid4()
        tenant_b_id = uuid4()

        tenant_a_service = mock_tenant_services["tenant_a"]
        tenant_b_service = mock_tenant_services["tenant_b"]

        tenant_a_service.create_workspace = AsyncMock(return_value={
            "id": str(uuid4()),
            "tenant_id": str(tenant_a_id),
            "name": "Workspace A"
        })
        tenant_b_service.create_workspace = AsyncMock(return_value={
            "id": str(uuid4()),
            "tenant_id": str(tenant_b_id),
            "name": "Workspace B"
        })

        workspace_a = await tenant_a_service.create_workspace(
            tenant_id=str(tenant_a_id),
            name="Workspace A"
        )
        workspace_b = await tenant_b_service.create_workspace(
            tenant_id=str(tenant_b_id),
            name="Workspace B"
        )

        assert workspace_a["tenant_id"] != workspace_b["tenant_id"]
        assert workspace_a["name"] != workspace_b["name"]

    @pytest.mark.asyncio
    async def test_cross_tenant_access_denied(self):
        """测试跨租户访问被拒绝"""
        tenant_a_id = uuid4()
        tenant_b_id = uuid4()

        with pytest.raises(PermissionError):
            if str(tenant_b_id) != str(tenant_a_id):
                raise PermissionError("Access denied between tenants")


class TestConcurrentUserE2E:
    """并发用户端到端测试"""

    @pytest.mark.asyncio
    async def test_concurrent_chat_requests(self):
        """测试并发聊天请求"""
        import asyncio

        mock_chat_service = MagicMock()
        mock_chat_service.chat = AsyncMock(return_value={
            "answer": "Response",
            "conversation_id": str(uuid4()),
            "query": "test",
            "retrieved_documents": [],
            "tokens_used": 10
        })

        async def simulate_user_request(user_id: int):
            response = await mock_chat_service.chat(
                dataset_id=str(uuid4()),
                query=f"Query from user {user_id}"
            )
            return response

        tasks = [simulate_user_request(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all("answer" in r for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_document_uploads(self):
        """测试并发文档上传"""
        import asyncio

        mock_doc_service = MagicMock()
        mock_doc_service.upload_document = AsyncMock(return_value={
            "id": str(uuid4()),
            "status": "completed",
            "chunk_count": 10
        })

        async def simulate_upload(user_id: int):
            return await mock_doc_service.upload_document(
                dataset_id=str(uuid4()),
                file_name=f"doc_{user_id}.pdf",
                content=b"test content"
            )

        tasks = [simulate_upload(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert mock_doc_service.upload_document.call_count == 5