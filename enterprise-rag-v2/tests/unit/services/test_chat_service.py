"""
单元测试 - 对话服务
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from core.interfaces.rag_engine import RAGResponse
from core.rag.rag_engine import RAGEngineImpl
from services.impl.chat_service import ChatServiceImpl
from infrastructure.database.models import Conversation, Message
from core.value_objects.pagination import Page, Pagination


class TestChatServiceImpl:
    """ChatServiceImpl单元测试"""

    @pytest.fixture
    def mock_session(self, sample_dataset_id):
        """创建模拟数据库会话：依次返回 workspace_id 列表与当前 workspace 下 dataset_id 列表。"""
        session = MagicMock()
        ws_id = uuid4()
        n = [0]

        async def _exec(*_a, **_k):
            n[0] += 1
            r = MagicMock()
            if n[0] == 1:
                r.scalars.return_value.all.return_value = [str(ws_id)]
            else:
                r.scalars.return_value.all.return_value = [str(sample_dataset_id)]
            r.scalar_one_or_none.return_value = None
            r.all.return_value = []
            return r

        session.execute = AsyncMock(side_effect=_exec)
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def chat_service(self, mock_session):
        """创建ChatServiceImpl实例"""
        return ChatServiceImpl(session=mock_session)

    @pytest.fixture(autouse=True)
    def _stub_rag_pipeline(self, sample_dataset_id):
        """避免单测拉起真实向量库 / LLM。"""
        resp = RAGResponse(
            answer="Response",
            retrieved_documents=[],
            tokens_used=1,
            retrieval_time_ms=1,
            generation_time_ms=1,
            metadata={},
        )
        with patch.object(RAGEngineImpl, "query", new_callable=AsyncMock, return_value=resp), \
             patch("core.rag.vector_store.create_vector_store", new_callable=AsyncMock) as mvs, \
             patch("core.rag.embedding.get_embedding_service", return_value=MagicMock()):
            mvs.return_value = MagicMock()
            yield

    @pytest.fixture
    def sample_user_id(self):
        return str(uuid4())

    @pytest.fixture
    def sample_dataset_id(self):
        """示例数据集ID"""
        return uuid4()

    @pytest.fixture
    def sample_conversation_id(self):
        """示例会话ID"""
        return uuid4()

    @pytest.mark.asyncio
    async def test_chat_creates_new_conversation(self, chat_service, sample_dataset_id, sample_user_id):
        """测试发送消息时创建新会话"""
        conversation_id = uuid4()

        with patch.object(chat_service, 'create_conversation', new_callable=AsyncMock) as mock_create_conv, \
             patch.object(chat_service, '_save_message', new_callable=AsyncMock) as mock_save:

            mock_create_conv.return_value = {
                "id": str(conversation_id),
                "dataset_id": str(sample_dataset_id),
                "title": "Test query",
                "created_at": datetime.utcnow().isoformat()
            }

            mock_save.return_value = {
                "id": str(uuid4()),
                "role": "assistant",
                "content": "Response",
                "created_at": datetime.utcnow().isoformat()
            }

            result = await chat_service.chat(
                dataset_id=sample_dataset_id,
                query="Test query",
                user_id=sample_user_id,
            )

            mock_create_conv.assert_called_once()
            assert result["conversation_id"] == str(conversation_id)

    @pytest.mark.asyncio
    async def test_chat_with_existing_conversation(self, chat_service, sample_dataset_id, sample_conversation_id):
        """测试使用现有会话发送消息"""
        with patch.object(chat_service, '_save_message', new_callable=AsyncMock) as mock_save:

            mock_save.return_value = {
                "id": str(uuid4()),
                "role": "assistant",
                "content": "Response",
                "created_at": datetime.utcnow().isoformat()
            }

            result = await chat_service.chat(
                dataset_id=sample_dataset_id,
                query="Test query",
                conversation_id=sample_conversation_id,
            )

            assert result["conversation_id"] == str(sample_conversation_id)
            mock_save.assert_called()

    @pytest.mark.asyncio
    async def test_chat_returns_response_structure(self, chat_service, sample_dataset_id, sample_user_id):
        """测试聊天返回正确的响应结构"""
        conversation_id = uuid4()

        with patch.object(chat_service, 'create_conversation', new_callable=AsyncMock) as mock_create_conv, \
             patch.object(chat_service, '_save_message', new_callable=AsyncMock) as mock_save:

            mock_create_conv.return_value = {
                "id": str(conversation_id),
                "dataset_id": str(sample_dataset_id),
                "title": "Test",
                "created_at": datetime.utcnow().isoformat()
            }

            message_id = uuid4()
            mock_save.return_value = {
                "id": str(message_id),
                "role": "assistant",
                "content": "Test response",
                "created_at": datetime.utcnow().isoformat()
            }

            result = await chat_service.chat(
                dataset_id=sample_dataset_id,
                query="Test query",
                user_id=sample_user_id,
            )

            assert "answer" in result
            assert "conversation_id" in result
            assert "query" in result
            assert "retrieved_documents" in result
            assert "tokens_used" in result
            assert "message_id" in result

    @pytest.mark.asyncio
    async def test_chat_stream_creates_new_conversation(self, chat_service, sample_dataset_id):
        """测试流式聊天时创建新会话"""
        conversation_id = uuid4()

        with patch.object(chat_service, 'create_conversation', new_callable=AsyncMock) as mock_create_conv:
            mock_create_conv.return_value = {
                "id": str(conversation_id),
                "dataset_id": str(sample_dataset_id),
                "title": "Test",
                "created_at": datetime.utcnow().isoformat()
            }

            async def mock_stream():
                yield "Test "
                yield "response"

            with patch.object(chat_service, 'chat_stream', return_value=mock_stream()):
                tokens = []
                async for token in chat_service.chat_stream(
                    dataset_id=sample_dataset_id,
                    query="Test query"
                ):
                    tokens.append(token)

                assert len(tokens) == 2

    @pytest.mark.asyncio
    async def test_create_conversation_success(self, chat_service, sample_dataset_id):
        """测试成功创建会话"""
        conversation_id = uuid4()

        mock_conv = MagicMock()
        mock_conv.id = conversation_id
        mock_conv.dataset_id = sample_dataset_id
        mock_conv.title = "New Conversation"
        mock_conv.metadata = {}
        mock_conv.created_at = datetime.utcnow()
        mock_conv.updated_at = datetime.utcnow()

        with patch.object(chat_service.conversation_repo, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_conv

            result = await chat_service.create_conversation(
                dataset_id=sample_dataset_id,
                user_id=str(uuid4()),
                title="New Conversation"
            )

            assert result["id"] == str(conversation_id)
            assert result["title"] == "New Conversation"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_conversation_without_title(self, chat_service, sample_dataset_id):
        """测试不提供标题创建会话"""
        conversation_id = uuid4()

        mock_conv = MagicMock()
        mock_conv.id = conversation_id
        mock_conv.dataset_id = sample_dataset_id
        mock_conv.title = "New conversation"
        mock_conv.metadata = {}
        mock_conv.created_at = datetime.utcnow()
        mock_conv.updated_at = datetime.utcnow()

        with patch.object(chat_service.conversation_repo, 'create', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_conv

            result = await chat_service.create_conversation(
                dataset_id=sample_dataset_id,
                user_id=str(uuid4()),
            )

            assert result["title"] == "New conversation"

    @pytest.mark.asyncio
    async def test_get_conversation_success(self, chat_service, sample_conversation_id):
        """测试成功获取会话"""
        mock_conv = MagicMock()
        mock_conv.id = sample_conversation_id
        mock_conv.dataset_id = uuid4()
        mock_conv.title = "Test Conversation"
        mock_conv.metadata = {}
        mock_conv.created_at = datetime.utcnow()
        mock_conv.updated_at = datetime.utcnow()

        with patch.object(chat_service.conversation_repo, 'get_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_conv

            result = await chat_service.get_conversation(sample_conversation_id)

            assert result is not None
            assert result["id"] == str(sample_conversation_id)
            assert result["title"] == "Test Conversation"

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, chat_service, sample_conversation_id):
        """测试获取不存在的会话"""
        with patch.object(chat_service.conversation_repo, 'get_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            result = await chat_service.get_conversation(sample_conversation_id)

            assert result is None

    @pytest.mark.asyncio
    async def test_update_conversation_success(self, chat_service, sample_conversation_id):
        """测试成功更新会话"""
        mock_conv = MagicMock()
        mock_conv.id = sample_conversation_id
        mock_conv.title = "Old Title"

        with patch.object(chat_service.conversation_repo, 'get_by_id', new_callable=AsyncMock) as mock_get, \
             patch.object(chat_service.conversation_repo, 'update', new_callable=AsyncMock) as mock_update:

            mock_get.return_value = mock_conv
            mock_update.return_value = mock_conv

            result = await chat_service.update_conversation(
                conversation_id=sample_conversation_id,
                title="New Title"
            )

            assert result is not None
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_conversation_not_found(self, chat_service, sample_conversation_id):
        """测试更新不存在的会话"""
        with patch.object(chat_service.conversation_repo, 'get_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(ValueError, match="会话不存在"):
                await chat_service.update_conversation(
                    conversation_id=sample_conversation_id,
                    title="New Title"
                )

    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, chat_service, sample_conversation_id):
        """测试成功删除会话"""
        mock_conv = MagicMock()
        mock_conv.id = sample_conversation_id

        with patch.object(chat_service.conversation_repo, 'get_by_id', new_callable=AsyncMock) as mock_get, \
             patch.object(chat_service.conversation_repo, 'delete', new_callable=AsyncMock) as mock_delete:

            mock_get.return_value = mock_conv
            mock_delete.return_value = True

            result = await chat_service.delete_conversation(sample_conversation_id)

            assert result is True
            mock_delete.assert_called_once_with(str(sample_conversation_id))

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, chat_service, sample_conversation_id):
        """测试删除不存在的会话"""
        with patch.object(chat_service.conversation_repo, 'get_by_id', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            result = await chat_service.delete_conversation(sample_conversation_id)

            assert result is False

    @pytest.mark.asyncio
    async def test_list_conversations(self, chat_service, sample_dataset_id):
        """测试查询会话列表（list_conversations 走 session.execute：先 count 再列表）"""
        mock_conv = MagicMock()
        mock_conv.id = uuid4()
        mock_conv.dataset_id = sample_dataset_id
        mock_conv.title = "Test"
        mock_conv.extra_metadata = {}
        mock_conv.created_at = datetime.utcnow()
        mock_conv.updated_at = datetime.utcnow()

        count_result = MagicMock()
        count_result.scalar.return_value = 1

        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [mock_conv]

        chat_service.session.execute = AsyncMock(side_effect=[count_result, list_result])

        result = await chat_service.list_conversations(
            dataset_id=sample_dataset_id
        )

        assert result.total == 1
        assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_get_conversation_messages(self, chat_service, sample_conversation_id):
        """测试获取会话消息历史"""
        message1 = MagicMock()
        message1.id = uuid4()
        message1.conversation_id = sample_conversation_id
        message1.role = "user"
        message1.content = "Hello"
        message1.retrieved_chunks = None
        message1.tokens_used = None
        message1.created_at = datetime.utcnow()

        message2 = MagicMock()
        message2.id = uuid4()
        message2.conversation_id = sample_conversation_id
        message2.role = "assistant"
        message2.content = "Hi there"
        message2.retrieved_chunks = []
        message2.tokens_used = 10
        message2.created_at = datetime.utcnow()

        with patch.object(chat_service.message_repo, 'get_by_conversation', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [message1, message2]

            result = await chat_service.get_conversation_messages(sample_conversation_id)

            assert len(result) == 2
            assert result[0]["role"] == "user"
            assert result[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_save_message_user(self, chat_service, sample_conversation_id):
        """测试保存用户消息"""
        message_id = uuid4()

        mock_message = MagicMock()
        mock_message.id = message_id
        mock_message.conversation_id = sample_conversation_id
        mock_message.role = "user"
        mock_message.content = "Test message"
        mock_message.tokens_used = None
        mock_message.created_at = datetime.utcnow()

        mock_conv = MagicMock()
        mock_conv.id = sample_conversation_id
        mock_conv.updated_at = datetime.utcnow()

        with patch.object(chat_service.message_repo, 'create', new_callable=AsyncMock) as mock_create_msg, \
             patch.object(chat_service.conversation_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_conv, \
             patch.object(chat_service.conversation_repo, 'update', new_callable=AsyncMock) as mock_update:

            mock_create_msg.return_value = mock_message
            mock_get_conv.return_value = mock_conv
            mock_update.return_value = mock_conv

            result = await chat_service._save_message(
                conversation_id=sample_conversation_id,
                role="user",
                content="Test message"
            )

            assert result["id"] == str(message_id)
            assert result["role"] == "user"
            assert result["content"] == "Test message"

    @pytest.mark.asyncio
    async def test_save_message_assistant(self, chat_service, sample_conversation_id):
        """测试保存助手消息"""
        message_id = uuid4()

        mock_message = MagicMock()
        mock_message.id = message_id
        mock_message.conversation_id = sample_conversation_id
        mock_message.role = "assistant"
        mock_message.content = "Response message"
        mock_message.tokens_used = 50
        mock_message.created_at = datetime.utcnow()

        mock_conv = MagicMock()
        mock_conv.id = sample_conversation_id
        mock_conv.updated_at = datetime.utcnow()

        with patch.object(chat_service.message_repo, 'create', new_callable=AsyncMock) as mock_create_msg, \
             patch.object(chat_service.conversation_repo, 'get_by_id', new_callable=AsyncMock) as mock_get_conv, \
             patch.object(chat_service.conversation_repo, 'update', new_callable=AsyncMock) as mock_update:

            mock_create_msg.return_value = mock_message
            mock_get_conv.return_value = mock_conv
            mock_update.return_value = mock_conv

            result = await chat_service._save_message(
                conversation_id=sample_conversation_id,
                role="assistant",
                content="Response message",
                tokens_used=50
            )

            assert result["id"] == str(message_id)
            assert result["role"] == "assistant"
            assert result["tokens_used"] == 50
