"""
pytest配置文件

提供共享的fixtures和测试配置
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

test_env_file = Path(__file__).parent / ".env.test"
if test_env_file.exists():
    with open(test_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                value = value.strip()
                if value.startswith("[") and value.endswith("]"):
                    import json
                    try:
                        value = json.dumps(json.loads(value))
                    except json.JSONDecodeError:
                        pass
                os.environ.setdefault(key.strip(), value)

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("TESTING", "true")
# 单元/集成测试使用 Mock，CSRF 会干扰非浏览器测试请求
os.environ.setdefault("CSRF_ENABLED", "false")
# 内部运维 /internal/admin：List[str] 需为合法 JSON（生产勿用）
os.environ.setdefault("INTERNAL_API_KEYS", '["test-internal-api-key-for-ci"]')
os.environ.setdefault("INTERNAL_IP_WHITELIST", '["*"]')

# 依赖本机 docker/requests 的探索脚本，默认不收集（见 pytest.ini norecursedirs=manual）
collect_ignore = ["test_bug_conditions.py"]

import asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环fixture"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_user_repo() -> MagicMock:
    """创建模拟用户Repository"""
    repo = MagicMock()
    repo.get_by_email = AsyncMock(return_value=None)
    repo.get_by_username = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.exists = AsyncMock(return_value=False)
    repo.list = AsyncMock()
    return repo


@pytest.fixture
def mock_tenant_repo() -> MagicMock:
    """创建模拟租户Repository"""
    repo = MagicMock()
    repo.get_by_email = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.list = AsyncMock()
    repo.exists = AsyncMock(return_value=False)
    return repo


@pytest.fixture
def mock_document_repo() -> MagicMock:
    """创建模拟文档Repository"""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.list = AsyncMock()
    repo.get_by_dataset = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_dataset_repo() -> MagicMock:
    """创建模拟数据集Repository"""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.list = AsyncMock()
    return repo


@pytest.fixture
def mock_workspace_repo() -> MagicMock:
    """创建模拟工作空间Repository"""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.list = AsyncMock()
    return repo


@pytest.fixture
def mock_conversation_repo() -> MagicMock:
    """创建模拟会话Repository"""
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=True)
    repo.list = AsyncMock()
    return repo


@pytest.fixture
def mock_message_repo() -> MagicMock:
    """创建模拟消息Repository"""
    repo = MagicMock()
    repo.get_by_conversation = AsyncMock(return_value=[])
    repo.create = AsyncMock()
    return repo


@pytest.fixture
def mock_cache() -> MagicMock:
    """创建模拟缓存"""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.exists = AsyncMock(return_value=False)
    return cache


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """创建模拟向量存储"""
    store = MagicMock()
    store.search = AsyncMock(return_value=[])
    store.insert = AsyncMock(return_value=True)
    store.batch_insert = AsyncMock(return_value=True)
    store.delete = AsyncMock(return_value=True)
    return store


@pytest.fixture
def mock_rag_engine() -> MagicMock:
    """创建模拟RAG引擎"""
    engine = MagicMock()
    engine.query = AsyncMock(return_value={
        "answer": "Test answer",
        "sources": [],
        "metadata": {}
    })
    engine.query_stream = AsyncMock(return_value=None)
    return engine


class MockUser:
    """模拟用户对象"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid4())
        self.username = kwargs.get("username", "testuser")
        self.email = kwargs.get("email", "test@example.com")
        self.hashed_password = kwargs.get("hashed_password", "$2b$12$test_hash")
        self.is_active = kwargs.get("is_active", True)
        self.is_superuser = kwargs.get("is_superuser", False)
        self.tenant_id = kwargs.get("tenant_id", None)
        self.extra_metadata = kwargs.get("extra_metadata", {})
        self.created_at = kwargs.get("created_at", datetime.utcnow())
        self.updated_at = kwargs.get("updated_at", datetime.utcnow())


class MockTenant:
    """模拟租户对象"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid4())
        self.name = kwargs.get("name", "Test Tenant")
        self.contact_email = kwargs.get("contact_email", "tenant@example.com")
        self.contact_phone = kwargs.get("contact_phone", "1234567890")
        self.plan = kwargs.get("plan", "free")
        self.status = kwargs.get("status", "active")
        self.extra_metadata = kwargs.get("extra_metadata", {})
        self.max_documents = kwargs.get("max_documents", 1000)
        self.max_storage_gb = kwargs.get("max_storage_gb", 10)
        self.created_at = kwargs.get("created_at", datetime.utcnow())
        self.updated_at = kwargs.get("updated_at", datetime.utcnow())


class MockWorkspace:
    """模拟工作空间对象"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid4())
        self.name = kwargs.get("name", "Test Workspace")
        self.description = kwargs.get("description", "")
        self.tenant_id = kwargs.get("tenant_id", uuid4())
        self.extra_metadata = kwargs.get("extra_metadata", {})
        self.created_at = kwargs.get("created_at", datetime.utcnow())
        self.updated_at = kwargs.get("updated_at", datetime.utcnow())


class MockDataset:
    """模拟数据集对象"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid4())
        self.name = kwargs.get("name", "Test Dataset")
        self.workspace_id = kwargs.get("workspace_id", uuid4())
        self.tenant_id = kwargs.get("tenant_id", uuid4())
        self.embedding_model = kwargs.get("embedding_model", "text-embedding-ada-002")
        self.chunk_size = kwargs.get("chunk_size", 500)
        self.chunk_overlap = kwargs.get("chunk_overlap", 50)
        self.extra_metadata = kwargs.get("extra_metadata", {})
        self.created_at = kwargs.get("created_at", datetime.utcnow())
        self.updated_at = kwargs.get("updated_at", datetime.utcnow())


class MockDocument:
    """模拟文档对象"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid4())
        self.dataset_id = kwargs.get("dataset_id", uuid4())
        self.file_name = kwargs.get("file_name", "test.pdf")
        self.file_type = kwargs.get("file_type", "pdf")
        self.file_size = kwargs.get("file_size", 1024)
        self.file_path = kwargs.get("file_path", "/uploads/test.pdf")
        self.status = kwargs.get("status", "pending")
        self.chunk_count = kwargs.get("chunk_count", 0)
        self.extra_metadata = kwargs.get("extra_metadata", {})
        self.created_at = kwargs.get("created_at", datetime.utcnow())
        self.indexed_at = kwargs.get("indexed_at", None)


class MockConversation:
    """模拟会话对象"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid4())
        self.dataset_id = kwargs.get("dataset_id", uuid4())
        self.title = kwargs.get("title", "Test Chat")
        self.extra_metadata = kwargs.get("extra_metadata", {})
        self.created_at = kwargs.get("created_at", datetime.utcnow())
        self.updated_at = kwargs.get("updated_at", datetime.utcnow())


class MockMessage:
    """模拟消息对象"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", uuid4())
        self.conversation_id = kwargs.get("conversation_id", uuid4())
        self.role = kwargs.get("role", "user")
        self.content = kwargs.get("content", "Hello")
        self.retrieved_chunks = kwargs.get("retrieved_chunks", None)
        self.tokens_used = kwargs.get("tokens_used", 0)
        self.extra_metadata = kwargs.get("extra_metadata", {})
        self.created_at = kwargs.get("created_at", datetime.utcnow())


@pytest.fixture
def sample_user() -> MockUser:
    """创建示例用户"""
    return MockUser(
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$test_hash",
        is_active=True,
        is_superuser=False
    )


@pytest.fixture
def sample_tenant() -> MockTenant:
    """创建示例租户"""
    return MockTenant(
        name="Test Tenant",
        contact_email="tenant@example.com",
        plan="free",
        status="active"
    )


@pytest.fixture
def sample_workspace(sample_tenant) -> MockWorkspace:
    """创建示例工作空间"""
    return MockWorkspace(
        name="Test Workspace",
        tenant_id=sample_tenant.id
    )


@pytest.fixture
def sample_dataset(sample_workspace) -> MockDataset:
    """创建示例数据集"""
    return MockDataset(
        name="Test Dataset",
        workspace_id=sample_workspace.id,
        tenant_id=sample_workspace.tenant_id
    )


@pytest.fixture
def sample_document(sample_dataset) -> MockDocument:
    """创建示例文档"""
    return MockDocument(
        dataset_id=sample_dataset.id,
        file_name="test.pdf"
    )


@pytest.fixture
def valid_password() -> str:
    """有效密码"""
    return "TestPass123!"


@pytest.fixture
def weak_password() -> str:
    """弱密码"""
    return "weak"


@pytest.fixture
def password_without_uppercase() -> str:
    """缺少大写字母的密码"""
    return "testpass123"


@pytest.fixture
def mock_settings():
    """模拟设置"""
    with patch("core.config.get_settings") as mock:
        settings = MagicMock()
        settings.auth.jwt_secret = "test-secret-key"
        settings.auth.jwt_algorithm = "HS256"
        settings.auth.access_token_expire_minutes = 30
        settings.auth.refresh_token_expire_days = 7
        settings.redis.url = "redis://localhost:6379/0"
        settings.redis.pool_size = 10
        settings.database.url = "sqlite+aiosqlite:///:memory:"
        mock.return_value = settings
        yield settings


@pytest.fixture
def empty_async_session():
    """SQLAlchemy AsyncSession 测试替身：execute 返回空结果，避免 AsyncMock 未 await / result.all 异常。"""
    session = MagicMock()
    result = MagicMock()
    result.all.return_value = []
    result.scalars.return_value.all.return_value = []
    result.scalar_one_or_none.return_value = None
    result.first.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock(return_value=None)
    session.refresh = AsyncMock()
    return session
