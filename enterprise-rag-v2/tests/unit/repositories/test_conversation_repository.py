"""
ConversationRepository单元测试
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from infrastructure.repositories.conversation_repository import (
    ConversationRepositoryImpl,
    MessageRepositoryImpl
)
from infrastructure.database.models import Conversation, Message


class MockSession:
    """模拟数据库会话"""
    def __init__(self):
        self.added = []
        self.flushed = False
        self.refreshed = []
        self.deleted = []

    def add(self, entity):
        self.added.append(entity)

    async def flush(self):
        self.flushed = True

    async def refresh(self, entity):
        self.refreshed.append(entity)

    async def execute(self, query):
        return MockResult()


class MockResult:
    """模拟查询结果"""
    def __init__(self, rowcount=1):
        self._rowcount = rowcount

    @property
    def rowcount(self):
        return self._rowcount

    def scalars(self):
        return MockScalars([])

    def scalar_one(self):
        return 0

    def scalar_one_or_none(self):
        return None


class MockScalars:
    """模拟标量结果"""
    def __init__(self, data):
        self._data = data

    def all(self):
        return self._data

    def one_or_none(self):
        return self._data[0] if self._data else None


class TestConversationRepository:
    """ConversationRepository测试"""

    @pytest.fixture
    def mock_session(self):
        return MockSession()

    @pytest.fixture
    def repo(self, mock_session):
        return ConversationRepositoryImpl(mock_session)

    @pytest.fixture
    def sample_conversation_id(self):
        return uuid4()

    @pytest.fixture
    def sample_dataset_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_conversation(self, repo, mock_session, sample_dataset_id):
        """测试创建会话"""
        conversation = Conversation(
            id=uuid4(),
            dataset_id=sample_dataset_id,
            title="Test Chat",
            metadata={}
        )

        result = await repo.create(conversation)

        assert conversation in mock_session.added
        assert mock_session.flushed is True
        assert conversation in mock_session.refreshed

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo, sample_conversation_id):
        """测试根据ID获取会话"""
        result = await repo.get_by_id(sample_conversation_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_dataset(self, repo, sample_dataset_id):
        """测试获取数据集下的会话"""
        result = await repo.get_by_dataset(sample_dataset_id)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_update_conversation(self, repo, mock_session, sample_dataset_id):
        """测试更新会话"""
        conversation = Conversation(
            id=uuid4(),
            dataset_id=sample_dataset_id,
            title="Original",
            metadata={}
        )

        result = await repo.update(conversation)

        assert mock_session.flushed is True
        assert conversation in mock_session.refreshed

    @pytest.mark.asyncio
    async def test_delete_conversation(self, repo, mock_session, sample_conversation_id):
        """测试删除会话"""
        result = await repo.delete(sample_conversation_id)

        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_exists_conversation(self, repo, sample_conversation_id):
        """测试检查会话是否存在"""
        result = await repo.exists(sample_conversation_id)
        assert result is False


class TestMessageRepository:
    """MessageRepository测试"""

    @pytest.fixture
    def mock_session(self):
        return MockSession()

    @pytest.fixture
    def repo(self, mock_session):
        return MessageRepositoryImpl(mock_session)

    @pytest.fixture
    def sample_message_id(self):
        return uuid4()

    @pytest.fixture
    def sample_conversation_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_message(self, repo, mock_session, sample_conversation_id):
        """测试创建消息"""
        message = Message(
            id=uuid4(),
            conversation_id=sample_conversation_id,
            role="user",
            content="Hello"
        )

        result = await repo.create(message)

        assert message in mock_session.added
        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_get_by_id(self, repo, sample_message_id):
        """测试根据ID获取消息"""
        result = await repo.get_by_id(sample_message_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_conversation(self, repo, sample_conversation_id):
        """测试获取会话下的消息"""
        result = await repo.get_by_conversation(sample_conversation_id)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_count_by_conversation(self, repo, sample_conversation_id):
        """测试统计会话消息数量"""
        result = await repo.count_by_conversation(sample_conversation_id)
        assert result == 0

    @pytest.mark.asyncio
    async def test_update_message(self, repo, mock_session, sample_conversation_id):
        """测试更新消息"""
        message = Message(
            id=uuid4(),
            conversation_id=sample_conversation_id,
            role="user",
            content="Original"
        )

        result = await repo.update(message)

        assert mock_session.flushed is True
        assert message in mock_session.refreshed

    @pytest.mark.asyncio
    async def test_delete_message(self, repo, mock_session, sample_message_id):
        """测试删除消息"""
        result = await repo.delete(sample_message_id)

        assert mock_session.flushed is True

    @pytest.mark.asyncio
    async def test_exists_message(self, repo, sample_message_id):
        """测试检查消息是否存在"""
        result = await repo.exists(sample_message_id)
        assert result is False
