"""
SQLAlchemy数据库模型

定义所有数据库表的ORM模型
"""

from datetime import datetime, timezone
from uuid import uuid4


def _utcnow() -> datetime:
    """返回带时区的 UTC 时间，匹配 PostgreSQL TIMESTAMP WITH TIME ZONE。"""
    return datetime.now(timezone.utc)
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Date, Text, JSON,
    ForeignKey, Index, UniqueConstraint, CheckConstraint, Enum as SQLEnum, Numeric,
    TypeDecorator,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum


Base = declarative_base()


class UuidType(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, str):
            return value
        return str(value)


def UUIDColumn():
    return Column(UuidType(), primary_key=True, default=lambda: str(uuid4()))


class UuidForeignKeyType(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, str):
            return value
        return str(value)


def UUIDForeignKey(table_name, nullable=True):
    return Column(
        UuidForeignKeyType(),
        ForeignKey(f"{table_name}.id", ondelete="CASCADE"),
        nullable=nullable
    )


# ============ 枚举类型 ============

class TenantStatus(str, enum.Enum):
    """租户状态"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class SubscriptionPlan(str, enum.Enum):
    """历史数据库字段枚举；开源版不据此区分功能。"""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class WorkspaceRole(str, enum.Enum):
    """工作空间角色"""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


def _coerce_workspace_role(value) -> WorkspaceRole:
    if isinstance(value, WorkspaceRole):
        return value
    if isinstance(value, str):
        s = value.strip()
        try:
            return WorkspaceRole(s)
        except ValueError:
            pass
        u = s.upper()
        if u in WorkspaceRole.__members__:
            return WorkspaceRole[u]
    return WorkspaceRole.MEMBER


class WorkspaceRoleColumn(TypeDecorator):
    """兼容 Alembic/PostgreSQL 枚举标签（OWNER）与 ORM 使用的 value（owner）及 SQLite 字符串存储。"""

    impl = String(20)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
            return dialect.type_descriptor(
                PG_ENUM("OWNER", "ADMIN", "MEMBER", "VIEWER", name="workspacerole", create_type=False)
            )
        return dialect.type_descriptor(String(20))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        e = _coerce_workspace_role(value)
        if dialect.name == "postgresql":
            return e.name
        return e.value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            s = value.strip()
            if s.upper() in WorkspaceRole.__members__:
                return WorkspaceRole[s.upper()]
            try:
                return WorkspaceRole(s)
            except ValueError:
                return WorkspaceRole.MEMBER
        return _coerce_workspace_role(str(value))


class DocumentStatus(str, enum.Enum):
    """文档状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentType(str, enum.Enum):
    """文档格式类型"""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"
    HTML = "html"
    EPUB = "epub"
    IMAGE = "image"
    XLSX = "xlsx"
    XLS = "xls"
    CSV = "csv"


class AssetSourceType(str, enum.Enum):
    """统一素材的来源类型。"""
    FILE = "file"
    URL = "url"
    TEXT = "text"
    CHAT = "chat"


class AssetStatus(str, enum.Enum):
    """统一素材的处理状态。"""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class KnowledgeType(str, enum.Enum):
    """知识分层类型 — 不同层次的知识有不同的组织方式和检索权重"""
    TOPIC = "topic"           # 领域全景，导航性质
    CONCEPT = "concept"       # 深度概念，需要完整保留上下文
    SUMMARY = "summary"       # 项目复盘/学习路径
    RECIPE = "recipe"         # 操作手册/检查清单，步骤性
    REFERENCE = "reference"   # API 参考/原始文档
    ERRATA = "errata"         # 勘误/已知问题


class ThemeMode(str, enum.Enum):
    """主题模式"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class Language(str, enum.Enum):
    """语言"""
    ZH_CN = "zh-CN"
    EN_US = "en-US"


# ============ 租户表 ============

class Tenant(Base):
    """租户表"""
    __tablename__ = "tenants"

    id = UUIDColumn()
    name = Column(String(100), nullable=False)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50))
    plan = Column(SQLEnum(SubscriptionPlan), nullable=False, default=SubscriptionPlan.FREE)
    status = Column(SQLEnum(TenantStatus), nullable=False, default=TenantStatus.ACTIVE)
    extra_metadata = Column("metadata", JSON, default=dict)
    # 数据库中的时间字段为 TIMESTAMP WITH TIME ZONE；显式声明 timezone
    # 避免 asyncpg 在用户登录后更新 current_workspace_id 时混用 naive/aware datetime。
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    workspaces = relationship("Workspace", back_populates="tenant", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_tenant_status", "status"),
        Index("idx_tenant_plan", "plan"),
        Index("idx_tenant_email", "contact_email"),
    )


# ============ 用户表 ============

class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    current_workspace_id = UUIDForeignKey("workspaces", nullable=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_superuser = Column(Boolean, nullable=False, default=False)
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tenant = relationship("Tenant", back_populates="users")
    workspace_members = relationship("WorkspaceMember", back_populates="user", cascade="all, delete-orphan")
    # Optional in the legacy production schema; avoid loading a missing table
    # during tenant deletion when OAuth is not installed.
    oauth_accounts = relationship("OAuthAccount", back_populates="user", cascade="all, delete-orphan", lazy="noload")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    # Legacy audit schema stores user_id as text; do not lazy-load it during
    # tenant deletion where the current model expects UUID.
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan", lazy="noload")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    user_configs = relationship("UserConfig", back_populates="user", cascade="all, delete-orphan")
    user_api_keys = relationship("UserAPIKey", back_populates="user", cascade="all, delete-orphan")
    # Optional in the legacy production schema; avoid loading a missing table
    # during tenant deletion when login activity is not installed.
    login_activities = relationship("LoginActivity", back_populates="user", cascade="all, delete-orphan", lazy="noload")
    current_workspace = relationship("Workspace", foreign_keys=[current_workspace_id])

    __table_args__ = (
        Index("idx_user_tenant", "tenant_id"),
        Index("idx_user_email", "email"),
        Index("idx_user_username", "username"),
        Index("idx_user_current_workspace", "current_workspace_id"),
    )


# ============ 工作空间表 ============

class Workspace(Base):
    """工作空间表"""
    __tablename__ = "workspaces"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    is_default = Column(Boolean, nullable=False, default=False)
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    tenant = relationship("Tenant", back_populates="workspaces")
    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")
    datasets = relationship("Dataset", back_populates="workspace", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_workspace_tenant", "tenant_id"),
        Index("idx_workspace_name", "name"),
    )


# ============ 工作空间成员表 ============

class WorkspaceMember(Base):
    """工作空间成员表"""
    __tablename__ = "workspace_members"

    id = UUIDColumn()
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    user_id = UUIDForeignKey("users", nullable=False)
    role = Column(WorkspaceRoleColumn(), nullable=False, default=WorkspaceRole.MEMBER)
    joined_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", back_populates="workspace_members")

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),
        Index("idx_workspace_member_workspace", "workspace_id"),
        Index("idx_workspace_member_user", "user_id"),
    )


# ============ 数据集表 ============

class Dataset(Base):
    """数据集表"""
    __tablename__ = "datasets"

    id = UUIDColumn()
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    is_public = Column(Boolean, nullable=False, default=False)
    embedding_model = Column(String(255), nullable=False)
    chunk_size = Column(Integer, nullable=False, default=500)
    chunk_overlap = Column(Integer, nullable=False, default=50)
    dataset_type = Column(
        String(20), nullable=False, default="GENERAL", server_default="GENERAL"
    )
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    workspace = relationship("Workspace", back_populates="datasets")
    documents = relationship("Document", back_populates="dataset", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="dataset", cascade="all, delete-orphan")
    equipment_models = relationship("EquipmentModel", back_populates="dataset")

    __table_args__ = (
        Index("idx_dataset_workspace", "workspace_id"),
        Index("idx_dataset_name", "name"),
    )


# ============ 文档表 ============

class Document(Base):
    """文档表"""
    __tablename__ = "documents"

    id = UUIDColumn()
    dataset_id = UUIDForeignKey("datasets", nullable=False)
    file_name = Column(String(255), nullable=False)
    file_type = Column(SQLEnum(DocumentType), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String(500), nullable=False)
    status = Column(SQLEnum(DocumentStatus), nullable=False, default=DocumentStatus.PENDING)
    knowledge_type = Column(SQLEnum(KnowledgeType, values_callable=lambda x: [e.value for e in x]), nullable=True, default=None)
    tags = Column(JSON, default=list)
    extra_metadata = Column("metadata", JSON, default=dict)
    chunk_count = Column(Integer, default=0)
    indexed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    dataset = relationship("Dataset", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_document_dataset", "dataset_id"),
        Index("idx_document_status", "status"),
        Index("idx_document_type", "file_type"),
        Index("idx_document_knowledge_type", "knowledge_type"),
    )


# ============ 统一素材表（AI 工作台 P0） ============

class Asset(Base):
    """素材统一入口；现有 Document/RAG 链路通过 legacy_document_id 兼容。"""
    __tablename__ = "assets"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    dataset_id = UUIDForeignKey("datasets", nullable=True)
    batch_id = UUIDForeignKey("ingestion_batches", nullable=True)
    created_by = UUIDForeignKey("users", nullable=False)
    legacy_document_id = Column(
        UuidType(),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    source_type = Column(String(32), nullable=False)
    title = Column(String(255), nullable=False)
    source_uri = Column(Text, nullable=True)
    storage_key = Column(String(512), nullable=True)
    source_etag = Column(String(255), nullable=True)
    mime_type = Column(String(127), nullable=True)
    size_bytes = Column(Integer, nullable=False, default=0)
    content_hash = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default=AssetStatus.PENDING.value)
    processing_error = Column(Text, nullable=True)
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_asset_tenant_workspace", "tenant_id", "workspace_id"),
        Index("idx_asset_dataset", "dataset_id"),
        Index("idx_asset_workspace_status", "workspace_id", "status"),
        Index("idx_asset_content_hash", "content_hash"),
        Index("idx_asset_created_by", "created_by"),
        Index("idx_asset_batch", "batch_id"),
    )


class IngestionBatch(Base):
    """一次用户导入动作的聚合状态；单个素材仍独立保留可重试状态。"""
    __tablename__ = "ingestion_batches"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    dataset_id = UUIDForeignKey("datasets", nullable=False)
    created_by = UUIDForeignKey("users", nullable=False)
    status = Column(String(32), nullable=False, default="processing")
    total_count = Column(Integer, nullable=False, default=0)
    completed_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    options_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_ingestion_batch_workspace", "workspace_id", "created_at"),
        Index("idx_ingestion_batch_status", "workspace_id", "status"),
    )


# ============ 知识中心 P0 ============

class KnowledgeItem(Base):
    """可审核的知识卡片；结论必须通过 evidence 关联回原始素材。"""
    __tablename__ = "knowledge_items"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    created_by = UUIDForeignKey("users", nullable=False)
    title = Column(String(255), nullable=False)
    item_type = Column(String(32), nullable=False, default="concept")
    definition = Column(Text, nullable=False, default="")
    details = Column(Text, nullable=True)
    conclusions = Column(JSON, default=list)
    confidence = Column(Float, nullable=False, default=0.5)
    review_status = Column(String(32), nullable=False, default="draft")
    reviewer_id = UUIDForeignKey("users", nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_knowledge_item_workspace_status", "workspace_id", "review_status"),
        Index("idx_knowledge_item_tenant", "tenant_id"),
        Index("idx_knowledge_item_created_at", "created_at"),
    )


class KnowledgeEvidence(Base):
    """知识卡片的证据片段，至少绑定一个 Asset 或兼容 Document。"""
    __tablename__ = "knowledge_evidence"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    knowledge_item_id = UUIDForeignKey("knowledge_items", nullable=False)
    asset_id = UUIDForeignKey("assets", nullable=True)
    document_id = UUIDForeignKey("documents", nullable=True)
    chunk_id = UUIDForeignKey("document_chunks", nullable=True)
    research_evidence_id = UUIDForeignKey("research_evidence", nullable=True)
    quote = Column(Text, nullable=False)
    locator = Column(String(255), nullable=True)
    source_uri = Column(Text, nullable=True)
    created_by = UUIDForeignKey("users", nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_knowledge_evidence_item", "knowledge_item_id"),
        Index("idx_knowledge_evidence_asset", "asset_id"),
        Index("idx_knowledge_evidence_document", "document_id"),
    )


class KnowledgeItemVersion(Base):
    """知识卡片内容快照；回滚通过创建新版本完成，不覆盖历史。"""
    __tablename__ = "knowledge_item_versions"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    knowledge_item_id = UUIDForeignKey("knowledge_items", nullable=False)
    version = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    item_type = Column(String(32), nullable=False)
    definition = Column(Text, nullable=False, default="")
    details = Column(Text, nullable=True)
    conclusions = Column(JSON, default=list)
    confidence = Column(Float, nullable=False, default=0.5)
    extra_metadata = Column("metadata", JSON, default=dict)
    created_by = UUIDForeignKey("users", nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("knowledge_item_id", "version", name="uq_knowledge_item_version"),
        Index("idx_knowledge_item_version_item", "knowledge_item_id", "version"),
    )


class KnowledgeRelation(Base):
    """知识卡片之间的显式有向关系，关系本身不携带业务状态。"""
    __tablename__ = "knowledge_relations"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    source_item_id = UUIDForeignKey("knowledge_items", nullable=False)
    target_item_id = UUIDForeignKey("knowledge_items", nullable=False)
    relation_type = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    created_by = UUIDForeignKey("users", nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("source_item_id", "target_item_id", "relation_type", name="uq_knowledge_relation_edge"),
        Index("idx_knowledge_relation_workspace", "workspace_id", "created_at"),
        Index("idx_knowledge_relation_source", "source_item_id"),
        Index("idx_knowledge_relation_target", "target_item_id"),
    )


# ============ 研究洞察 P1 ============

class ResearchProject(Base):
    """用户可见的研究项目。"""
    __tablename__ = "research_projects"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    created_by = UUIDForeignKey("users", nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="active")
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_research_project_workspace", "workspace_id", "status"),
        Index("idx_research_project_tenant", "tenant_id"),
    )


class ResearchQuestion(Base):
    __tablename__ = "research_questions"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    project_id = UUIDForeignKey("research_projects", nullable=False)
    question = Column(Text, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (Index("idx_research_question_project", "project_id", "sort_order"),)


class ResearchSample(Base):
    __tablename__ = "research_samples"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    project_id = UUIDForeignKey("research_projects", nullable=False)
    asset_id = UUIDForeignKey("assets", nullable=True)
    dataset_id = UUIDForeignKey("datasets", nullable=True)
    source_uri = Column(Text, nullable=True)
    created_by = UUIDForeignKey("users", nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (Index("idx_research_sample_project", "project_id"),)


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    project_id = UUIDForeignKey("research_projects", nullable=False)
    created_by = UUIDForeignKey("users", nullable=False)
    status = Column(String(32), nullable=False, default="pending")
    plan = Column(JSON, default=dict)
    limits = Column(JSON, default=dict)
    progress = Column(Integer, nullable=False, default=0)
    current_stage = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (Index("idx_research_run_project_status", "project_id", "status"),)


class ResearchSource(Base):
    __tablename__ = "research_sources"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    run_id = UUIDForeignKey("research_runs", nullable=False)
    asset_id = UUIDForeignKey("assets", nullable=True)
    source_uri = Column(Text, nullable=True)
    title = Column(String(255), nullable=True)
    content_hash = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="available")
    captured_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (Index("idx_research_source_run", "run_id"),)


class ResearchEvidence(Base):
    __tablename__ = "research_evidence"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    run_id = UUIDForeignKey("research_runs", nullable=False)
    source_id = UUIDForeignKey("research_sources", nullable=False)
    quote = Column(Text, nullable=False)
    locator = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (Index("idx_research_evidence_run", "run_id"),)


class ResearchFinding(Base):
    __tablename__ = "research_findings"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    run_id = UUIDForeignKey("research_runs", nullable=False)
    claim = Column(Text, nullable=False)
    claim_type = Column(String(32), nullable=False, default="observation")
    confidence = Column(Float, nullable=False, default=0.5)
    evidence_ids = Column(JSON, default=list)
    needs_review = Column(Boolean, nullable=False, default=True)
    review_status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (Index("idx_research_finding_run", "run_id"),)


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    run_id = UUIDForeignKey("research_runs", nullable=False)
    version = Column(Integer, nullable=False, default=1)
    content_markdown = Column(Text, nullable=False, default="")
    content_json = Column(JSON, default=dict)
    model_name = Column(String(128), nullable=True)
    prompt_version = Column(String(64), nullable=True)
    citation_completeness = Column(Float, nullable=False, default=0)
    review_status = Column(String(32), nullable=False, default="draft")
    published_dataset_id = UUIDForeignKey("datasets", nullable=True)
    published_document_id = UUIDForeignKey("documents", nullable=True)
    published_knowledge_item_id = UUIDForeignKey("knowledge_items", nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_research_report_workspace", "workspace_id"),
        UniqueConstraint("run_id", name="uq_research_report_run"),
    )


class AgentDefinition(Base):
    """可审计的显式工作流定义，不允许在运行时动态注入任意工具。"""
    __tablename__ = "agent_definitions"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    created_by = UUIDForeignKey("users", nullable=False)
    name = Column(String(255), nullable=False)
    agent_type = Column(String(64), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    workflow = Column(JSON, nullable=False, default=list)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (Index("idx_agent_definition_workspace", "workspace_id", "status"),)


class AgentRun(Base):
    """一次工作流运行；研究运行通过 research_run_id 复用研究业务主表。"""
    __tablename__ = "agent_runs"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    definition_id = UUIDForeignKey("agent_definitions", nullable=False)
    research_run_id = UUIDForeignKey("research_runs", nullable=True)
    created_by = UUIDForeignKey("users", nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    input_json = Column(JSON, nullable=False, default=dict)
    config_json = Column(JSON, nullable=False, default=dict)
    current_step = Column(String(64), nullable=True)
    progress = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_agent_run_workspace_status", "workspace_id", "status"),
        UniqueConstraint("research_run_id", name="uq_agent_run_research_run"),
    )


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    agent_run_id = UUIDForeignKey("agent_runs", nullable=False)
    step_key = Column(String(64), nullable=False)
    step_order = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="pending")
    input_json = Column(JSON, nullable=False, default=dict)
    output_json = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_agent_step_run_order", "agent_run_id", "step_order"),
        UniqueConstraint("agent_run_id", "step_key", name="uq_agent_run_step_key"),
    )


class AgentOutput(Base):
    __tablename__ = "agent_outputs"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    agent_run_id = UUIDForeignKey("agent_runs", nullable=False)
    step_id = UUIDForeignKey("agent_run_steps", nullable=True)
    output_type = Column(String(64), nullable=False)
    title = Column(String(255), nullable=True)
    content_text = Column(Text, nullable=True)
    content_json = Column(JSON, nullable=False, default=dict)
    review_status = Column(String(32), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (Index("idx_agent_output_run", "agent_run_id"),)


class AgentApproval(Base):
    __tablename__ = "agent_approvals"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    agent_run_id = UUIDForeignKey("agent_runs", nullable=False)
    step_id = UUIDForeignKey("agent_run_steps", nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    reviewer_id = UUIDForeignKey("users", nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("idx_agent_approval_run_status", "agent_run_id", "status"),)


class AgentSchedule(Base):
    """持久化的研究 Agent 调度；调度器只负责投递，不在 beat 进程执行业务。"""
    __tablename__ = "agent_schedules"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    definition_id = UUIDForeignKey("agent_definitions", nullable=False)
    project_id = UUIDForeignKey("research_projects", nullable=False)
    created_by = UUIDForeignKey("users", nullable=False)
    name = Column(String(255), nullable=False)
    schedule_expression = Column(String(128), nullable=False)
    timezone = Column(String(64), nullable=False, default="Asia/Shanghai")
    config_json = Column(JSON, nullable=False, default=dict)
    enabled = Column(Boolean, nullable=False, default=True)
    next_run_at = Column(DateTime(timezone=True), nullable=False)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_id = UUIDForeignKey("research_runs", nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (Index("idx_agent_schedule_due", "enabled", "next_run_at"), Index("idx_agent_schedule_workspace", "workspace_id"))


class ContentTopic(Base):
    """内容选题；只保存内容策划，不与外部平台发布耦合。"""
    __tablename__ = "content_topics"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    created_by = UUIDForeignKey("users", nullable=False)
    title = Column(String(255), nullable=False)
    brief = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="idea")
    tags = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (Index("idx_content_topic_workspace_status", "workspace_id", "status"),)


class ContentDraft(Base):
    __tablename__ = "content_drafts"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    topic_id = UUIDForeignKey("content_topics", nullable=True)
    created_by = UUIDForeignKey("users", nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="draft")
    review_status = Column(String(32), nullable=False, default="pending")
    reviewer_id = UUIDForeignKey("users", nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (Index("idx_content_draft_workspace_review", "workspace_id", "review_status"),)


class ContentPublishRecord(Base):
    __tablename__ = "content_publish_records"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    draft_id = UUIDForeignKey("content_drafts", nullable=False)
    platform = Column(String(64), nullable=False)
    credential_id = UUIDForeignKey("content_connector_credentials", nullable=True)
    status = Column(String(32), nullable=False, default="published")
    external_id = Column(String(255), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    response_json = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (Index("idx_content_publish_draft", "draft_id"), Index("idx_content_publish_workspace", "workspace_id"))


class ContentConnectorCredential(Base):
    """内容连接器凭据；只保存 Fernet 密文，明文只在一次发布调用内解密。"""
    __tablename__ = "content_connector_credentials"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    platform = Column(String(64), nullable=False)
    name = Column(String(100), nullable=False)
    encrypted_credentials = Column(Text, nullable=False)
    credential_hint = Column(String(255), nullable=False, default="已配置")
    status = Column(String(32), nullable=False, default="active")
    created_by = UUIDForeignKey("users", nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        UniqueConstraint("workspace_id", "platform", "name", name="uq_content_credential_workspace_platform_name"),
        Index("idx_content_credential_workspace", "workspace_id", "platform", "status"),
    )


class ContentMetric(Base):
    __tablename__ = "content_metrics"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    publish_record_id = UUIDForeignKey("content_publish_records", nullable=False)
    impressions = Column(Integer, nullable=False, default=0)
    clicks = Column(Integer, nullable=False, default=0)
    likes = Column(Integer, nullable=False, default=0)
    comments = Column(Integer, nullable=False, default=0)
    shares = Column(Integer, nullable=False, default=0)
    raw_json = Column(JSON, nullable=False, default=dict)
    collected_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (Index("idx_content_metric_publish", "publish_record_id", "collected_at"),)


class ContentMetricSyncRun(Base):
    """平台指标同步任务；保存状态和结果，便于前端轮询及审计。"""
    __tablename__ = "content_metric_sync_runs"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    credential_id = UUIDForeignKey("content_connector_credentials", nullable=True)
    platform = Column(String(64), nullable=False)
    requested_by = UUIDForeignKey("users", nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    payload_json = Column(JSON, nullable=False, default=dict)
    inserted = Column(Integer, nullable=False, default=0)
    skipped = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    task_id = Column(String(255), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (Index("idx_content_metric_sync_workspace", "workspace_id", "created_at"), Index("idx_content_metric_sync_status", "status", "created_at"))


class ContentRetrospective(Base):
    __tablename__ = "content_retrospectives"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    publish_record_id = UUIDForeignKey("content_publish_records", nullable=False)
    summary = Column(Text, nullable=False)
    recommendations = Column(JSON, nullable=False, default=list)
    metric_snapshot = Column(JSON, nullable=False, default=dict)
    created_by = UUIDForeignKey("users", nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (Index("idx_content_retro_publish", "publish_record_id", "created_at"),)


# ============ 文档块表 ============

class DocumentChunk(Base):
    """文档块表"""
    __tablename__ = "document_chunks"

    id = UUIDColumn()
    document_id = UUIDForeignKey("documents", nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk"),
        Index("idx_chunk_document", "document_id"),
    )


class DocumentAnnotation(Base):
    """阅读台中的可追溯笔记/理解标注。"""
    __tablename__ = "document_annotations"

    id = UUIDColumn()
    tenant_id = UUIDForeignKey("tenants", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=False)
    document_id = UUIDForeignKey("documents", nullable=False)
    author_id = UUIDForeignKey("users", nullable=False)
    kind = Column(String(32), nullable=False, default="note")
    quote = Column(Text, nullable=False, default="")
    body = Column(Text, nullable=False)
    question = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_document_annotation_document", "document_id", "created_at"),
        Index("idx_document_annotation_workspace", "workspace_id", "created_at"),
    )


# ============ 文档复制状态表 ============

class DocumentCopyStatus(Base):
    """文档复制状态追踪表"""
    __tablename__ = "document_copy_status"

    id = UUIDColumn()
    dataset_id = UUIDForeignKey("datasets", nullable=False)
    task_id = Column(String(255), nullable=True)  # Celery task ID
    total_documents = Column(Integer, default=0)
    completed_documents = Column(Integer, default=0)
    failed_documents = Column(Integer, default=0)
    status = Column(String(50), default="pending")  # pending/processing/completed/failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_copy_status_dataset", "dataset_id"),
        Index("idx_copy_status_status", "status"),
    )


# ============ 勘误表 ============

class ErrataSeverity(str, enum.Enum):
    """勘误严重程度"""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    NOTE = "note"


class ErrataStatus(str, enum.Enum):
    """勘误状态"""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class DocumentErrata(Base):
    """文档勘误表 — 记录知识库中已发现的不准确或过时内容"""
    __tablename__ = "document_errata"

    # 024 迁移在 PostgreSQL 中将该主键建为 varchar(36)，不能使用通用
    # UUIDColumn（它会把绑定参数声明为 PostgreSQL UUID）。
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    errata_code = Column(String(20), nullable=False, unique=True)  # E-001, E-002, ...
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    # 迁移脚本创建的 PostgreSQL enum 使用业务值（如 `open`），而
    # SQLAlchemy 默认会持久化 Enum 成员名（如 `OPEN`）。显式指定
    # values_callable，确保 SQLite/PostgreSQL 与 API 的小写状态契约一致。
    severity = Column(
        SQLEnum(ErrataSeverity, values_callable=lambda enum_type: [item.value for item in enum_type]),
        nullable=False,
        default=ErrataSeverity.MINOR,
    )
    status = Column(
        SQLEnum(ErrataStatus, values_callable=lambda enum_type: [item.value for item in enum_type]),
        nullable=False,
        default=ErrataStatus.OPEN,
    )
    fix_suggestion = Column(Text, nullable=True)
    source_evidence = Column(Text, nullable=True)
    affected_document_ids = Column(JSON, default=list)  # [doc_id, ...]
    related_document_ids = Column(JSON, default=list)    # [doc_id, ...] for context
    reported_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_errata_severity", "severity"),
        Index("idx_errata_status", "status"),
        Index("idx_errata_code", "errata_code"),
    )


# ============ 会话可见性枚举 ============

class ConversationVisibility(str, enum.Enum):
    """会话可见性级别"""
    PRIVATE = "private"
    WORKSPACE = "workspace"
    TENANT = "tenant"


# ============ 会话表 ============

class Conversation(Base):
    """会话表（支持权限管理）"""
    __tablename__ = "conversations"

    id = UUIDColumn()
    dataset_id = UUIDForeignKey("datasets", nullable=False)
    user_id = UUIDForeignKey("users", nullable=False)
    workspace_id = UUIDForeignKey("workspaces", nullable=True)
    title = Column(String(255))
    visibility = Column(
        String(20),
        nullable=False,
        default=ConversationVisibility.PRIVATE,
        comment="会话可见性: private|workspace|tenant"
    )
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    dataset = relationship("Dataset", back_populates="conversations")
    user = relationship("User", back_populates="conversations")
    workspace = relationship("Workspace")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_conversation_dataset", "dataset_id"),
        Index("idx_conversation_user", "user_id"),
        Index("idx_conversation_visibility", "visibility"),
        Index("idx_conversation_workspace", "workspace_id"),
        Index("idx_conversation_user_visibility", "user_id", "visibility"),
        Index("idx_conversation_workspace_visibility", "workspace_id", "visibility"),
    )


# ============ 消息表 ============

class Message(Base):
    """消息表"""
    __tablename__ = "messages"

    id = UUIDColumn()
    conversation_id = UUIDForeignKey("conversations", nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    retrieved_chunks = Column(JSON)
    tokens_used = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("idx_message_conversation", "conversation_id"),
        Index("idx_message_role", "role"),
    )


# ============ OAuth账户表 ============

class OAuthAccount(Base):
    """OAuth账户表"""
    __tablename__ = "oauth_accounts"

    id = UUIDColumn()
    user_id = UUIDForeignKey("users", nullable=False)
    provider = Column(String(50), nullable=False)
    provider_user_id = Column(String(255), nullable=False)
    access_token = Column(Text)
    refresh_token = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="oauth_accounts")

    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
        Index("idx_oauth_user", "user_id"),
        Index("idx_oauth_provider", "provider"),
    )


# ============ 审计日志表 ============

class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"

    id = UUIDColumn()
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(255))
    user_id = UUIDForeignKey("users", nullable=True)
    tenant_id = UUIDForeignKey("tenants", nullable=True)
    workspace_id = UUIDForeignKey("workspaces", nullable=True)
    ip_address = Column(String(50))
    user_agent = Column(Text)
    details = Column(JSON, default=dict)
    status = Column(String(20), default="success")
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_user", "user_id"),
        Index("idx_audit_tenant", "tenant_id"),
        Index("idx_audit_action", "action"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_created", "created_at"),
    )


# ============ API密钥表 ============

class APIKey(Base):
    """API密钥表（系统API访问）"""
    __tablename__ = "api_keys"

    id = UUIDColumn()
    user_id = UUIDForeignKey("users", nullable=False)
    name = Column(String(100), nullable=False)
    key_hash = Column(String(255), nullable=False)
    last_used_at = Column(DateTime(timezone=True))
    expires_at = Column(DateTime(timezone=True))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    user = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index("idx_api_key_user", "user_id"),
        Index("idx_api_key_hash", "key_hash"),
    )


# ============ 用户配置表 ============

class UserConfig(Base):
    """用户配置表"""
    __tablename__ = "user_configs"

    id = UUIDColumn()
    user_id = UUIDForeignKey("users", nullable=False)
    
    # 系统设置
    # 迁移以 VARCHAR 保存偏好值；关闭 PostgreSQL 原生 enum，兼容已有数据库和 SQLite 测试库。
    theme = Column(SQLEnum(ThemeMode, native_enum=False, length=20), nullable=False, default=ThemeMode.LIGHT)
    language = Column(SQLEnum(Language, native_enum=False, length=20), nullable=False, default=Language.ZH_CN)
    default_page = Column(String(100), nullable=False, default="/")
    
    # 模型配置
    embedding_model = Column(String(255), nullable=False, default="bge-small-zh-v1.5")
    llm_model = Column(String(255), nullable=False, default="deepseek-chat")
    temperature = Column(Float, nullable=False, default=0.7)
    top_k = Column(Integer, nullable=False, default=5)
    
    # 安全设置
    session_timeout_minutes = Column(Integer, nullable=False, default=1440)
    two_factor_auth_enabled = Column(Boolean, nullable=False, default=False)
    ip_whitelist = Column(Text, nullable=True)
    
    # 扩展元数据
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="user_configs")
    
    __table_args__ = (
        Index("idx_user_config_user", "user_id"),
        UniqueConstraint("user_id", name="uq_user_config_user"),
    )


# ============ 用户API密钥表 ============

class UserAPIKey(Base):
    """用户API密钥表（用户配置的第三方API密钥）"""
    __tablename__ = "user_api_keys"

    id = UUIDColumn()
    user_id = UUIDForeignKey("users", nullable=False)
    
    provider = Column(String(50), nullable=False)  # openai, deepseek, etc.
    name = Column(String(100), nullable=False)
    api_key_encrypted = Column(Text, nullable=False)
    base_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", back_populates="user_api_keys")
    
    __table_args__ = (
        Index("idx_user_api_key_user", "user_id"),
        Index("idx_user_api_key_provider", "provider"),
    )


# ============ 登录活动表 ============

class LoginActivity(Base):
    """登录活动表"""
    __tablename__ = "login_activities"

    id = UUIDColumn()
    user_id = UUIDForeignKey("users", nullable=False)
    
    ip_address = Column(String(50), nullable=False)
    user_agent = Column(Text, nullable=True)
    location = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="success")
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    user = relationship("User", back_populates="login_activities")
    
    __table_args__ = (
        Index("idx_login_activity_user", "user_id"),
        Index("idx_login_activity_created", "created_at"),
    )


# ============ 运维中心模型 ============

class OpsOperationStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class OpsTaskEventType(str, enum.Enum):
    DISPATCHED = "DISPATCHED"
    STARTED = "STARTED"
    PROGRESS = "PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRY = "RETRY"


class OpsQuotaDimension(str, enum.Enum):
    USERS = "users"
    DOCUMENTS = "documents"
    STORAGE_MB = "storage_mb"
    API_CALLS_MONTHLY = "api_calls_monthly"
    CHAT_MESSAGES_MONTHLY = "chat_messages_monthly"
    WORKSPACES = "workspaces"


class OpsUser(Base):
    __tablename__ = "ops_users"

    id = UUIDColumn()
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    user_ref_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_ops_users_active", "is_active"),
    )


class OpsRole(Base):
    __tablename__ = "ops_roles"

    id = UUIDColumn()
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class OpsUserRole(Base):
    __tablename__ = "ops_user_roles"

    id = UUIDColumn()
    ops_user_id = Column(String(36), ForeignKey("ops_users.id", ondelete="CASCADE"), nullable=False)
    role_code = Column(String(50), ForeignKey("ops_roles.code", ondelete="CASCADE"), nullable=False)
    created_by = Column(String(36), ForeignKey("ops_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("ops_user_id", "role_code", name="uq_ops_user_role"),
        Index("idx_ops_user_roles_user", "ops_user_id"),
    )


class OpsOperation(Base):
    __tablename__ = "ops_operations"

    id = UUIDColumn()
    operation_id = Column(String(64), nullable=False, unique=True)
    operator_id = Column(String(36), nullable=True)
    operator_name = Column(String(100), nullable=False)
    target_env = Column(String(50), nullable=False)
    target_service = Column(String(100), nullable=False)
    cluster_id = Column(String(100), nullable=True)
    tenant_id = Column(String(36), nullable=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(255), nullable=True)
    request_payload = Column(JSON, nullable=False, default=dict)
    before_snapshot = Column(JSON, nullable=True)
    after_snapshot = Column(JSON, nullable=True)
    status = Column(SQLEnum(OpsOperationStatus), nullable=False, default=OpsOperationStatus.PENDING)
    error_message = Column(Text, nullable=True)
    audit_log_id = Column(String(36), ForeignKey("audit_logs.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String(36), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=True)
    source_ip = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_ops_operations_tenant_status_created", "tenant_id", "status", "created_at"),
        Index("idx_ops_operations_tenant_action_created", "tenant_id", "action", "created_at"),
        Index("idx_ops_operations_status_created", "status", "created_at"),
    )


class OpsTaskEvent(Base):
    __tablename__ = "ops_task_events"

    id = UUIDColumn()
    operation_id = Column(String(64), nullable=False)
    task_id = Column(String(100), nullable=False)
    event_type = Column(SQLEnum(OpsTaskEventType), nullable=False)
    message = Column(Text, nullable=True)
    payload = Column(JSON, nullable=False, default=dict)
    retry_count = Column(Integer, nullable=False, default=0)
    error_code = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_ops_task_events_operation", "operation_id"),
        Index("idx_ops_task_events_task_id", "task_id"),
        Index("idx_ops_task_events_created", "created_at"),
    )


class QuotaOverride(Base):
    __tablename__ = "quota_overrides"

    id = UUIDColumn()
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    dimension = Column(SQLEnum(OpsQuotaDimension), nullable=False)
    override_value = Column(Integer, nullable=False)
    reason = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(36), ForeignKey("ops_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_quota_overrides_tenant_dimension", "tenant_id", "dimension"),
        Index("idx_quota_overrides_expires_at", "expires_at"),
    )


# ============ IM 消息归档频道表 ============

class WebhookChannel(Base):
    """IM 消息归档频道 — 将群聊消息自动归档到知识库"""
    __tablename__ = "webhook_channels"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(64), nullable=False)
    dataset_id = Column(String(36), nullable=False)
    name = Column(String(100), nullable=False)
    provider = Column(String(20), nullable=False)  # wecom / feishu / dingtalk
    conversation_id = Column(String(255), nullable=True)  # IM侧会话ID（群聊ID）
    is_active = Column(Boolean, nullable=False, default=True)
    archive_enabled = Column(Boolean, nullable=False, default=True)
    config = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_webhook_channel_tenant", "tenant_id"),
        Index("idx_webhook_channel_dataset", "dataset_id"),
        Index("idx_webhook_channel_provider", "provider"),
        Index("idx_webhook_channel_conversation", "tenant_id", "provider", "conversation_id"),
    )


# ============================================================================
# 设备数据库（Equipment — 工控设备售前+售后 Agent）
# ============================================================================

class EquipmentCategory(Base):
    """设备分类表（树形层级：PLC/变频器/伺服/传感器...）"""
    __tablename__ = "equipment_categories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(64), nullable=False)
    parent_id = Column(String(36), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    icon = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_eq_cat_tenant", "tenant_id"),
        Index("idx_eq_cat_parent", "parent_id"),
    )


class EquipmentModel(Base):
    """设备型号表"""
    __tablename__ = "equipment_models"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(64), nullable=False)
    category_id = Column(String(36), ForeignKey("equipment_categories.id", ondelete="SET NULL"), nullable=True)
    dataset_id = Column(String(36), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    brand = Column(String(100), nullable=False)
    model = Column(String(200), nullable=False)
    series = Column(String(200), nullable=True)
    description = Column(Text)
    specifications = Column(JSON, default=dict)
    protocols = Column(JSON, default=list)
    image_url = Column(String(500), nullable=True)
    datasheet_path = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    category = relationship("EquipmentCategory")
    dataset = relationship("Dataset", back_populates="equipment_models")
    fault_codes = relationship("EquipmentFaultCode", back_populates="model", cascade="all, delete-orphan")
    parts = relationship("EquipmentPart", back_populates="model", cascade="all, delete-orphan")
    instances = relationship("EquipmentInstance", back_populates="model", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_eq_model_tenant", "tenant_id"),
        Index("idx_eq_model_brand", "brand"),
        Index("idx_eq_model_category", "category_id"),
        Index("idx_eq_model_brand_model", "brand", "model"),
    )


class EquipmentFaultCode(Base):
    """故障码库表（核心资产）"""
    __tablename__ = "equipment_fault_codes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(64), nullable=False)
    model_id = Column(String(36), ForeignKey("equipment_models.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False, default="medium")  # critical/high/medium/low
    meaning = Column(String(500), nullable=False)
    causes = Column(JSON, default=list)
    repair_steps = Column(JSON, default=list)
    related_parts = Column(JSON, default=list)
    safety_notes = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    model = relationship("EquipmentModel", back_populates="fault_codes")

    __table_args__ = (
        Index("idx_eq_fc_tenant", "tenant_id"),
        Index("idx_eq_fc_model", "model_id"),
        Index("idx_eq_fc_code", "model_id", "code"),
        UniqueConstraint("model_id", "code", name="uq_model_fault_code"),
    )


class EquipmentPart(Base):
    """配件库表"""
    __tablename__ = "equipment_parts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(64), nullable=False)
    model_id = Column(String(36), ForeignKey("equipment_models.id", ondelete="CASCADE"), nullable=False)
    part_number = Column(String(100), nullable=False)
    name = Column(String(200), nullable=False)
    specification = Column(String(500), nullable=True)
    supplier = Column(String(200), nullable=True)
    unit_price = Column(Numeric(12, 2), nullable=True)
    stock_quantity = Column(Integer, default=0)
    is_consumable = Column(Boolean, default=True)
    lead_time_days = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    model = relationship("EquipmentModel", back_populates="parts")

    __table_args__ = (
        Index("idx_eq_part_tenant", "tenant_id"),
        Index("idx_eq_part_model", "model_id"),
        Index("idx_eq_part_number", "model_id", "part_number"),
    )


class EquipmentMaintenanceRecord(Base):
    """维修记录表"""
    __tablename__ = "equipment_maintenance_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(64), nullable=False)
    model_id = Column(String(36), nullable=True)
    equipment_instance_id = Column(String(36), nullable=True)
    work_order_id = Column(String(36), nullable=True)
    fault_code = Column(String(50), nullable=True)
    fault_description = Column(Text, nullable=False)
    symptoms = Column(JSON, default=list)
    diagnosis_result = Column(JSON, nullable=True)
    repair_steps = Column(JSON, default=list)
    parts_used = Column(JSON, default=list)
    repair_time_minutes = Column(Integer, nullable=True)
    repair_result = Column(String(50), nullable=True)  # resolved / partial / failed / escalated
    technician = Column(String(100), nullable=True)
    vector_id = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_eq_mr_tenant", "tenant_id"),
        Index("idx_eq_mr_model", "model_id"),
        Index("idx_eq_mr_code", "fault_code"),
        Index("idx_eq_mr_vector", "vector_id"),
        Index("idx_eq_mr_instance", "equipment_instance_id"),
        Index("idx_eq_mr_work_order", "work_order_id"),
    )


class DiagnosisReport(Base):
    """诊断报告表"""
    __tablename__ = "diagnosis_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(64), nullable=False)
    request_params = Column(JSON, nullable=False)
    stage_results = Column(JSON, default=dict)
    report_content = Column(JSON, nullable=True)
    severity = Column(String(20), nullable=True)
    rating = Column(String(10), nullable=True)  # useful / useless
    feedback = Column(Text, nullable=True)
    work_order_id = Column(String(36), nullable=True)
    actual_fault_cause = Column(Text, nullable=True)
    diagnosis_accuracy = Column(String(20), nullable=True)  # correct / partial / incorrect
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_diag_tenant", "tenant_id"),
        Index("idx_diag_created", "tenant_id", "created_at"),
        Index("idx_diag_work_order", "work_order_id"),
    )


# ============================================================================
# Phase 2: 维修闭环 — 设备实例 + 工单 + 通知
# ============================================================================

class EquipmentInstance(Base):
    """设备实例表（部署在车间的具体设备，区别于 equipment_models 型号目录）"""
    __tablename__ = "equipment_instances"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(64), nullable=False)
    workspace_id = Column(String(36), nullable=True)
    model_id = Column(String(36), ForeignKey("equipment_models.id", ondelete="SET NULL"), nullable=False)
    dataset_id = Column(String(36), nullable=True)
    serial_number = Column(String(100), nullable=True)
    name = Column(String(200), nullable=True)
    location = Column(String(300), nullable=True)
    department = Column(String(100), nullable=True)
    status = Column(String(20), nullable=False, default="running")  # running/maintenance/fault/shutdown/retired
    installation_date = Column(Date, nullable=True)
    last_maintenance_at = Column(DateTime(timezone=True), nullable=True)
    next_maintenance_at = Column(DateTime(timezone=True), nullable=True)
    running_hours = Column(Integer, default=0)
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    model = relationship("EquipmentModel", back_populates="instances")

    __table_args__ = (
        Index("idx_ei_tenant", "tenant_id"),
        Index("idx_ei_model", "model_id"),
        Index("idx_ei_status", "status"),
        Index("idx_ei_location", "tenant_id", "location"),
        UniqueConstraint("tenant_id", "serial_number", name="uq_ei_serial"),
    )


class WorkOrder(Base):
    """维修工单表 — 6态状态机: open→assigned→in_progress→completed→verified；任意阶段→cancelled"""
    __tablename__ = "work_orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(64), nullable=False)
    workspace_id = Column(String(36), nullable=True)
    diagnosis_report_id = Column(String(36), nullable=True)
    equipment_instance_id = Column(String(36), nullable=True)
    model_id = Column(String(36), nullable=True)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    priority = Column(String(10), nullable=False, default="medium")  # critical/high/medium/low
    status = Column(String(20), nullable=False, default="open")  # open/assigned/in_progress/completed/verified/cancelled
    fault_cause = Column(Text, nullable=True)
    assigned_to = Column(String(36), nullable=True)
    created_by = Column(String(36), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    repair_duration_min = Column(Integer, nullable=True)
    repair_result = Column(Text, nullable=True)
    repair_steps_executed = Column(JSON, default=list)
    parts_consumed = Column(JSON, default=list)
    safety_notes_executed = Column(JSON, default=list)
    before_photos = Column(JSON, default=list)
    after_photos = Column(JSON, default=list)
    notes = Column(Text, nullable=True)
    version = Column(Integer, default=1)  # 乐观锁
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_wo_tenant", "tenant_id"),
        Index("idx_wo_status", "tenant_id", "status"),
        Index("idx_wo_assigned", "assigned_to", "status"),
        Index("idx_wo_instance", "equipment_instance_id"),
        Index("idx_wo_diagnosis", "diagnosis_report_id"),
        Index("idx_wo_created", "tenant_id", "created_at"),
        CheckConstraint(
            "status IN ('open','assigned','in_progress','completed','verified','cancelled')",
            name="ck_wo_status"
        ),
        CheckConstraint(
            "priority IN ('critical','high','medium','low')",
            name="ck_wo_priority"
        ),
    )


class Notification(Base):
    """消息通知表"""
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    tenant_id = Column(String(64), nullable=False)
    user_id = Column(String(36), nullable=False)
    type = Column(String(30), nullable=False)  # work_order_assigned/work_order_updated/diagnosis_completed/equipment_alert/maintenance_due/part_low_stock
    title = Column(String(200), nullable=False)
    body = Column(Text)
    ref_type = Column(String(30), nullable=True)  # work_order/diagnosis_report/equipment_instance
    ref_id = Column(String(36), nullable=True)
    is_read = Column(Boolean, default=False)
    push_channel = Column(String(20), default="in_app")  # in_app/feishu/dingtalk/wecom/email
    push_status = Column(String(20), default="pending")  # pending/sent/failed
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_notif_user", "user_id", "is_read", "created_at"),
        Index("idx_notif_tenant", "tenant_id", "created_at"),
        Index("idx_notif_ref", "ref_type", "ref_id"),
    )# ============ 学习诊断引擎 ============

class LearningSubject(Base):
    """学科定义"""
    __tablename__ = "learning_subjects"

    id = UUIDColumn()
    name = Column(String(50), nullable=False)
    grade_level = Column(String(20), nullable=False, comment="junior_high / senior_high / primary")
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_learning_subject_name", "name"),
        Index("idx_learning_subject_grade", "grade_level"),
    )


class LearningTextbookVersion(Base):
    """教材版本"""
    __tablename__ = "learning_textbook_versions"

    id = UUIDColumn()
    subject_id = UUIDForeignKey("learning_subjects", nullable=False)
    publisher = Column(String(100), nullable=False, comment="出版社")
    grade = Column(Integer, nullable=False, comment="年级")
    semester = Column(Integer, nullable=False, comment="学期 1或2")
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_learning_tv_subject", "subject_id"),
        Index("idx_learning_tv_grade", "grade"),
        UniqueConstraint("subject_id", "publisher", "grade", "semester", name="uq_learning_tv"),
    )


class LearningKnowledgePoint(Base):
    """知识点图谱 — 树形结构 + 前置依赖"""
    __tablename__ = "learning_knowledge_points"

    id = UUIDColumn()
    subject_id = UUIDForeignKey("learning_subjects", nullable=False)
    textbook_version_id = UUIDForeignKey("learning_textbook_versions", nullable=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), nullable=True, comment="知识点编码如 M8-C3-KP01")
    parent_id = UUIDForeignKey("learning_knowledge_points", nullable=True)
    chapter = Column(String(200), nullable=True)
    page_range = Column(String(50), nullable=True, comment="教材页码范围")
    difficulty_level = Column(Integer, nullable=False, default=3, comment="1-5")
    prerequisite_kp_ids = Column(JSON, default=list, comment="前置知识点ID列表")
    sort_order = Column(Integer, default=0)
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_learning_kp_subject", "subject_id"),
        Index("idx_learning_kp_tv", "textbook_version_id"),
        Index("idx_learning_kp_parent", "parent_id"),
        Index("idx_learning_kp_code", "code"),
        Index("idx_learning_kp_difficulty", "difficulty_level"),
    )


class LearningMaterial(Base):
    """教材/教辅原文素材 — 向量化后可被RAG检索"""
    __tablename__ = "learning_materials"

    id = UUIDColumn()
    knowledge_point_id = UUIDForeignKey("learning_knowledge_points", nullable=False)
    textbook_version_id = UUIDForeignKey("learning_textbook_versions", nullable=True)
    content_type = Column(String(50), nullable=False, comment="textbook / explanation / example / common_mistake")
    title = Column(String(300), nullable=True)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    vector_id = Column(String(200), nullable=True, comment="Milvus向量ID")
    chunk_index = Column(Integer, default=0)
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_learning_mat_kp", "knowledge_point_id"),
        Index("idx_learning_mat_tv", "textbook_version_id"),
        Index("idx_learning_mat_type", "content_type"),
        Index("idx_learning_mat_vector", "vector_id"),
    )


class LearningDiagnosisReport(Base):
    """学习诊断报告"""
    __tablename__ = "learning_diagnosis_reports"

    id = UUIDColumn()
    user_id = UUIDForeignKey("users", nullable=False)
    subject_id = UUIDForeignKey("learning_subjects", nullable=False)
    textbook_version_id = UUIDForeignKey("learning_textbook_versions", nullable=True)
    grade_level = Column(String(20), nullable=True)

    # 诊断输入
    input_type = Column(String(50), nullable=False, default="manual", comment="manual / photo / self_test")
    question_text = Column(Text, nullable=False)
    original_images = Column(JSON, default=list, comment="原始试卷/错题照片URLs")
    original_answer = Column(Text, nullable=True, comment="学生作答内容")
    kp_code = Column(String(50), nullable=True)
    error_tags = Column(JSON, default=list)

    # 诊断结果
    weak_knowledge_points = Column(JSON, default=list, comment="[{kp_id, name, mastery_level, confidence}]")
    error_analysis = Column(JSON, default=list, comment="[{error_type, description, frequency}]")
    overall_mastery_score = Column(Integer, nullable=True, comment="综合掌握度 0-100")

    # 5阶段记录
    stage_results = Column(JSON, default=dict)
    report_content = Column(JSON, default=dict)

    # 关联闭环
    practice_session_id = UUIDForeignKey("learning_practice_sessions", nullable=True)

    # 反馈
    rating = Column(String(20), nullable=True)
    feedback = Column(Text, nullable=True)

    status = Column(String(20), default="completed")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_learning_report_user", "user_id"),
        Index("idx_learning_report_subject", "subject_id"),
        Index("idx_learning_report_status", "status"),
        Index("idx_learning_report_created", "created_at"),
        Index("idx_learning_report_user_subject", "user_id", "subject_id"),
    )


class LearningPracticeSession(Base):
    """靶向练习会话 — 状态机: generated → in_progress → completed → verified"""
    __tablename__ = "learning_practice_sessions"

    id = UUIDColumn()
    diagnosis_report_id = UUIDForeignKey("learning_diagnosis_reports", nullable=False)
    user_id = UUIDForeignKey("users", nullable=False)
    knowledge_point_ids = Column(JSON, default=list, comment="涉及的知识点ID列表")

    # 练习题目
    exercises = Column(JSON, default=list, comment="[{idx, question, answer, hints, kp_id}]")
    answers_submitted = Column(JSON, default=list, comment="[{idx, answer, correct, submitted_at}]")
    exercises_completed = Column(Integer, default=0)
    exercises_correct = Column(Integer, default=0)

    # 掌握度变化
    mastery_before = Column(Integer, nullable=True)
    mastery_after = Column(Integer, nullable=True)

    # 状态机
    status = Column(String(20), default="generated", comment="generated / in_progress / completed / verified / regenerated")

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_learning_ps_report", "diagnosis_report_id"),
        Index("idx_learning_ps_user", "user_id"),
        Index("idx_learning_ps_status", "status"),
        Index("idx_learning_ps_created", "created_at"),
    )


class LearningStudentProfile(Base):
    """学生学情档案"""
    __tablename__ = "learning_student_profiles"

    id = UUIDColumn()
    user_id = UUIDForeignKey("users", nullable=False)
    grade_level = Column(String(20), nullable=True)
    subjects = Column(JSON, default=list, comment="已选学科ID列表")
    knowledge_mastery = Column(JSON, default=dict, comment="{kp_id: {mastery, last_tested_at, trend}}")
    total_diagnoses = Column(Integer, default=0)
    total_practice_sessions = Column(Integer, default=0)
    avg_mastery_score = Column(Integer, nullable=True)
    extra_metadata = Column("metadata", JSON, default=dict)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_learning_profile_user", "user_id"),
        Index("idx_learning_profile_grade", "grade_level"),
    )


class LearningErrorRecord(Base):
    """学生错误案例库 — 脱敏后供 Stage3 同类错误匹配"""
    __tablename__ = "learning_error_records"

    id = UUIDColumn()
    knowledge_point_id = UUIDForeignKey("learning_knowledge_points", nullable=False)
    error_type = Column(String(100), nullable=False, comment="计算错误 / 概念不清 / 审题失误 / ...")
    error_description = Column(Text, nullable=False)
    correct_approach = Column(Text, nullable=True)
    frequency = Column(Integer, default=1, comment="同类错误出现频次")
    extra_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("idx_learning_err_kp", "knowledge_point_id"),
        Index("idx_learning_err_type", "error_type"),
    )
