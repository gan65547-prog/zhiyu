"""
API路由层测试 - 对话路由

测试对话相关的API端点
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock


class TestChatRouter:
    """对话路由测试"""

    @pytest.fixture
    def mock_chat_service(self):
        service = MagicMock()
        service.chat = AsyncMock(return_value={
            "conversation_id": str(uuid4()),
            "query": "test query",
            "answer": "test answer",
            "message_id": str(uuid4()),
            "retrieved_documents": [],
            "tokens_used": 100
        })
        async def _create_conversation(**kwargs):
            did = kwargs.get("dataset_id")
            title = kwargs.get("title") or "Test Conversation"
            return {
                "id": str(uuid4()),
                "dataset_id": str(did) if did is not None else str(uuid4()),
                "title": title,
            }

        service.create_conversation = AsyncMock(side_effect=_create_conversation)
        service.get_conversation = AsyncMock(return_value={
            "id": str(uuid4()),
            "title": "Test Conversation"
        })
        service.update_conversation = AsyncMock(return_value={
            "id": str(uuid4()),
            "title": "Updated Title"
        })
        service.delete_conversation = AsyncMock(return_value=True)
        service.list_conversations = AsyncMock(return_value=MagicMock(
            items=[{"id": str(uuid4()), "title": "Test"}],
            total=1,
            page=1,
            page_size=20
        ))
        service.get_conversation_messages = AsyncMock(return_value=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ])
        return service

    @pytest.mark.asyncio
    async def test_chat_success(self, mock_chat_service):
        """测试发送对话请求成功"""
        result = await mock_chat_service.chat(
            dataset_id=uuid4(),
            query="What is this about?"
        )

        assert result["answer"] == "test answer"
        assert result["conversation_id"] is not None

    @pytest.mark.asyncio
    async def test_chat_with_conversation_id(self, mock_chat_service):
        """测试带会话ID的对话"""
        result = await mock_chat_service.chat(
            dataset_id=uuid4(),
            query="Follow up question",
            conversation_id=uuid4()
        )

        assert result["answer"] == "test answer"

    @pytest.mark.asyncio
    async def test_create_conversation_success(self, mock_chat_service):
        """测试创建会话成功"""
        result = await mock_chat_service.create_conversation(
            dataset_id=uuid4(),
            title="New Conversation"
        )

        assert result["title"] == "New Conversation"

    @pytest.mark.asyncio
    async def test_get_conversation_success(self, mock_chat_service):
        """测试获取会话成功"""
        result = await mock_chat_service.get_conversation(uuid4())

        assert result["title"] == "Test Conversation"

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, mock_chat_service):
        """测试获取不存在的会话"""
        mock_chat_service.get_conversation = AsyncMock(return_value=None)

        result = await mock_chat_service.get_conversation(uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_update_conversation_success(self, mock_chat_service):
        """测试更新会话成功"""
        result = await mock_chat_service.update_conversation(
            conversation_id=uuid4(),
            title="Updated Title"
        )

        assert result["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, mock_chat_service):
        """测试删除会话成功"""
        result = await mock_chat_service.delete_conversation(uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, mock_chat_service):
        """测试删除不存在的会话"""
        mock_chat_service.delete_conversation = AsyncMock(return_value=False)

        result = await mock_chat_service.delete_conversation(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_list_conversations_success(self, mock_chat_service):
        """测试查询会话列表成功"""
        result = await mock_chat_service.list_conversations(dataset_id=uuid4())

        assert result.total == 1
        assert len(result.items) == 1

    @pytest.mark.asyncio
    async def test_get_conversation_messages_success(self, mock_chat_service):
        """测试获取会话消息成功"""
        result = await mock_chat_service.get_conversation_messages(uuid4())

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
