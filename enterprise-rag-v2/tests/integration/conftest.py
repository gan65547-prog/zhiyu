"""
集成测试配置

提供集成测试共享的fixtures
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("TESTING", "true")
os.environ.setdefault("CSRF_ENABLED", "false")  # 集成测试需禁用 CSRF
os.environ.setdefault("INTERNAL_API_KEYS", '["test-internal-api-key-for-ci"]')
os.environ.setdefault("INTERNAL_IP_WHITELIST", '["*"]')

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4


@pytest.fixture
def mock_db_session():
    """创建模拟数据库会话"""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_cache():
    """创建模拟缓存"""
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.exists = AsyncMock(return_value=False)
    return cache


@pytest.fixture
def mock_redis():
    """创建模拟Redis客户端"""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=False)
    return redis


@pytest.fixture
def sample_user_data():
    """示例用户数据"""
    return {
        "id": uuid4(),
        "username": "testuser",
        "email": "test@example.com",
        "hashed_password": "$2b$12$test_hash",
        "is_active": True,
        "is_superuser": False,
        "tenant_id": uuid4()
    }


@pytest.fixture
def sample_tenant_data():
    """示例租户数据"""
    return {
        "id": uuid4(),
        "name": "Test Tenant",
        "contact_email": "tenant@example.com",
        "plan": "free",
        "status": "active",
        "max_documents": 1000,
        "max_storage_gb": 10
    }


@pytest.fixture
def sample_workspace_data():
    """示例工作空间数据"""
    return {
        "id": uuid4(),
        "name": "Test Workspace",
        "description": "Test workspace",
        "tenant_id": uuid4()
    }


@pytest.fixture
def sample_dataset_data():
    """示例数据集数据"""
    return {
        "id": uuid4(),
        "name": "Test Dataset",
        "workspace_id": uuid4(),
        "tenant_id": uuid4(),
        "embedding_model": "text-embedding-ada-002",
        "chunk_size": 500,
        "chunk_overlap": 50
    }


@pytest.fixture
def sample_document_data():
    """示例文档数据"""
    return {
        "id": uuid4(),
        "dataset_id": uuid4(),
        "file_name": "test.pdf",
        "file_type": "pdf",
        "file_size": 1024,
        "file_path": "/uploads/test.pdf",
        "status": "pending",
        "chunk_count": 0
    }


@pytest.fixture
def auth_headers():
    """认证头"""
    return {
        "Authorization": "Bearer test_token"
    }
