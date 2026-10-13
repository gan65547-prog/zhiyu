"""
集成测试 - 对话流程

测试对话相关的集成场景
使用真实的ChatServiceImpl但Mock数据库层
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.impl.chat_service import ChatServiceImpl
from infrastructure.database.models import Conversation, Message


class MockConversationRepo:
    """模拟会话Repository"""
    def __init__(self):
        self.conversations = {}

    async def get_by_id(self, conversation_id):
        return self.conversations.get(str(conversation_id))

    async def create(self, conversation: Conversation):
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

    async def update(self, conversation: Conversation):
        if not conversation.updated_at:
            from datetime import datetime
            conversation.updated_at = datetime.utcnow()
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
        if filters and "dataset_id" in filters:
            items = [c for c in items if c.dataset_id == filters["dataset_id"]]
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

    async def create(self, message: Message):
        key = str(message.conversation_id)
        if key not in self.messages:
            self.messages[key] = []
        self.messages[key].append(message)
        return message


class TestChatFlowIntegration:
    """对话流程集成测试"""

    @pytest.fixture
    def mock_db_session(self):
        """创建模拟数据库会话"""
        class _Result:
            def __init__(self, scalar=None, rows=None):
                self._scalar = scalar
                self._rows = rows or []

            def scalar(self):
                return self._scalar

            def scalar_one_or_none(self):
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
        session.execute = AsyncMock(side_effect=[_Result(scalar=0), _Result(rows=[])])
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.fixture
    def chat_service(self, mock_db_session):
        """创建ChatServiceImpl实例"""
        service = ChatServiceImpl(session=mock_db_session)
        service.conversation_repo = MockConversationRepo()
        service.message_repo = MockMessageRepo()
        return service

    @pytest.fixture
    def sample_dataset_id(self):
        """示例数据集ID"""
        return uuid4()

    @pytest.fixture
    def sample_conversation_id(self):
        """示例会话ID"""
        return uuid4()

    @pytest.fixture
    def sample_user_id(self):
        return str(uuid4())

    @pytest.mark.asyncio
    async def test_chat_creates_new_conversation(self, chat_service, sample_dataset_id, sample_user_id):
        """测试发送消息时创建新会话"""
        result = await chat_service.chat(
            dataset_id=sample_dataset_id,
            query="Test query",
            user_id=sample_user_id,
        )

        assert result["conversation_id"] is not None
        assert result["query"] == "Test query"
        assert "answer" in result
        assert "message_id" in result

    @pytest.mark.asyncio
    async def test_chat_with_existing_conversation(self, chat_service, sample_dataset_id, sample_conversation_id, sample_user_id):
        """测试使用现有会话发送消息"""
        conv = Conversation(
            id=sample_conversation_id,
            dataset_id=sample_dataset_id,
            user_id=sample_user_id,
            title="Existing Chat",
            metadata={}
        )
        chat_service.conversation_repo.conversations[str(sample_conversation_id)] = conv

        result = await chat_service.chat(
            dataset_id=sample_dataset_id,
            query="Test query",
            conversation_id=sample_conversation_id,
            user_id=sample_user_id,
        )

        assert result["conversation_id"] == str(sample_conversation_id)
        assert result["query"] == "Test query"

    @pytest.mark.asyncio
    async def test_chat_rejects_foreign_conversation(self, chat_service, sample_dataset_id, sample_conversation_id, sample_user_id):
        """会话 ID 属于其他用户时不得续写，防止水平越权。"""
        foreign_user_id = str(uuid4())
        chat_service.conversation_repo.conversations[str(sample_conversation_id)] = Conversation(
            id=sample_conversation_id,
            dataset_id=sample_dataset_id,
            user_id=foreign_user_id,
            title="Foreign Chat",
            metadata={},
        )

        with pytest.raises(PermissionError, match="无权写入"):
            await chat_service.chat(
                dataset_id=sample_dataset_id,
                query="Test query",
                conversation_id=sample_conversation_id,
                user_id=sample_user_id,
            )

    @pytest.mark.asyncio
    async def test_create_conversation_success(self, chat_service, sample_dataset_id, sample_user_id):
        """测试成功创建会话"""
        result = await chat_service.create_conversation(
            dataset_id=sample_dataset_id,
            user_id=sample_user_id,
            title="New Chat"
        )

        assert result["id"] is not None
        assert result["title"] == "New Chat"
        assert result["dataset_id"] == str(sample_dataset_id)

    @pytest.mark.asyncio
    async def test_create_conversation_without_title(self, chat_service, sample_dataset_id, sample_user_id):
        """测试不提供标题创建会话"""
        result = await chat_service.create_conversation(
            dataset_id=sample_dataset_id,
            user_id=sample_user_id,
        )

        assert result["id"] is not None
        assert "New conversation" in result["title"]

    @pytest.mark.asyncio
    async def test_get_conversation_success(self, chat_service, sample_dataset_id, sample_conversation_id):
        """测试成功获取会话"""
        conv = Conversation(
            id=sample_conversation_id,
            dataset_id=sample_dataset_id,
            title="Test Chat",
            metadata={}
        )
        chat_service.conversation_repo.conversations[str(sample_conversation_id)] = conv

        result = await chat_service.get_conversation(sample_conversation_id)

        assert result is not None
        assert result["id"] == str(sample_conversation_id)
        assert result["title"] == "Test Chat"

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, chat_service, sample_conversation_id):
        """测试获取不存在的会话"""
        result = await chat_service.get_conversation(sample_conversation_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_conversation_success(self, chat_service, sample_dataset_id, sample_conversation_id):
        """测试成功更新会话"""
        conv = Conversation(
            id=sample_conversation_id,
            dataset_id=sample_dataset_id,
            title="Old Title",
            metadata={}
        )
        chat_service.conversation_repo.conversations[str(sample_conversation_id)] = conv

        result = await chat_service.update_conversation(
            conversation_id=sample_conversation_id,
            title="New Title"
        )

        assert result["title"] == "New Title"

    @pytest.mark.asyncio
    async def test_update_conversation_not_found(self, chat_service, sample_conversation_id):
        """测试更新不存在的会话"""
        with pytest.raises(ValueError, match="会话不存在"):
            await chat_service.update_conversation(
                conversation_id=sample_conversation_id,
                title="New Title"
            )

    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, chat_service, sample_dataset_id, sample_conversation_id):
        """测试成功删除会话"""
        conv = Conversation(
            id=sample_conversation_id,
            dataset_id=sample_dataset_id,
            title="To Delete",
            metadata={}
        )
        chat_service.conversation_repo.conversations[str(sample_conversation_id)] = conv

        result = await chat_service.delete_conversation(sample_conversation_id)
        assert result is True
        assert str(sample_conversation_id) not in chat_service.conversation_repo.conversations

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, chat_service, sample_conversation_id):
        """测试删除不存在的会话"""
        result = await chat_service.delete_conversation(sample_conversation_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_list_conversations(self, chat_service, sample_dataset_id):
        """测试查询会话列表"""
        conv1 = Conversation(
            id=uuid4(),
            dataset_id=sample_dataset_id,
            title="Chat 1",
            metadata={}
        )
        conv2 = Conversation(
            id=uuid4(),
            dataset_id=sample_dataset_id,
            title="Chat 2",
            metadata={}
        )
        chat_service.conversation_repo.conversations[str(conv1.id)] = conv1
        chat_service.conversation_repo.conversations[str(conv2.id)] = conv2

        class _Result:
            def __init__(self, scalar=None, rows=None):
                self._scalar = scalar
                self._rows = rows or []

            def scalar(self):
                return self._scalar

            def scalar_one_or_none(self):
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

        chat_service.session.execute = AsyncMock(
            side_effect=[
                _Result(scalar=2),
                _Result(rows=[conv1, conv2]),
            ]
        )

        result = await chat_service.list_conversations(dataset_id=sample_dataset_id)

        assert result.total == 2
        assert len(result.items) == 2

    @pytest.mark.asyncio
    async def test_get_conversation_messages(self, chat_service, sample_dataset_id, sample_conversation_id):
        """测试获取会话消息历史"""
        conv = Conversation(
            id=sample_conversation_id,
            dataset_id=sample_dataset_id,
            title="Chat with Messages",
            metadata={}
        )
        chat_service.conversation_repo.conversations[str(sample_conversation_id)] = conv

        msg1 = Message(
            id=uuid4(),
            conversation_id=sample_conversation_id,
            role="user",
            content="Hello"
        )
        msg2 = Message(
            id=uuid4(),
            conversation_id=sample_conversation_id,
            role="assistant",
            content="Hi there!"
        )
        chat_service.message_repo.messages[str(sample_conversation_id)] = [msg1, msg2]

        result = await chat_service.get_conversation_messages(sample_conversation_id)

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        assert result[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_save_user_message(self, chat_service, sample_dataset_id, sample_conversation_id):
        """测试保存用户消息"""
        conv = Conversation(
            id=sample_conversation_id,
            dataset_id=sample_dataset_id,
            title="Chat",
            metadata={}
        )
        chat_service.conversation_repo.conversations[str(sample_conversation_id)] = conv

        result = await chat_service._save_message(
            conversation_id=sample_conversation_id,
            role="user",
            content="Test message"
        )

        assert result["role"] == "user"
        assert result["content"] == "Test message"
        assert "id" in result

    @pytest.mark.asyncio
    async def test_save_assistant_message(self, chat_service, sample_dataset_id, sample_conversation_id):
        """测试保存助手消息"""
        conv = Conversation(
            id=sample_conversation_id,
            dataset_id=sample_dataset_id,
            title="Chat",
            metadata={}
        )
        chat_service.conversation_repo.conversations[str(sample_conversation_id)] = conv

        result = await chat_service._save_message(
            conversation_id=sample_conversation_id,
            role="assistant",
            content="Test response",
            tokens_used=50
        )

        assert result["role"] == "assistant"
        assert result["content"] == "Test response"
        assert result["tokens_used"] == 50
