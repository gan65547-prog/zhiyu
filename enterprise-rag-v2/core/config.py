"""
系统配置管理

统一管理系统配置参数
"""

from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from functools import lru_cache
import os


def normalize_database_url(url: str) -> str:
    """
    将 SQLite 匿名内存库改为共享内存 URI，使 SQLAlchemy 的 create_all 与
    databases 包使用同一逻辑库，避免「表在 A 连接建了、B 连接查不到」导致 500。
    """
    if not url:
        return url
    u = url.strip()
    if u in (
        "sqlite+aiosqlite:///:memory:",
        "sqlite:///:memory:",
    ):
        return "sqlite+aiosqlite:///file:erag_shared?mode=memory&cache=shared&uri=true"
    return url


class DatabaseConfig(BaseSettings):
    """数据库配置"""
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    url: str = Field("sqlite+aiosqlite:///:memory:", env="DATABASE_URL")
    pool_size: int = Field(10, env="DB_POOL_SIZE")
    max_overflow: int = Field(20, env="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(30, env="DB_POOL_TIMEOUT")
    pool_pre_ping: bool = Field(True, env="DB_POOL_PRE_PING")
    pool_recycle: int = Field(3600, env="DB_POOL_RECYCLE")
    echo: bool = Field(False, env="DB_ECHO")


class RedisConfig(BaseSettings):
    """Redis配置"""
    url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    pool_size: int = Field(10, env="REDIS_POOL_SIZE")
    timeout: int = Field(5, env="REDIS_TIMEOUT")


class QdrantConfig(BaseSettings):
    """Qdrant 配置；嵌套 Settings 中 Field(env=) 不会绑定环境变量，需 validation_alias。"""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    url: str = Field(default="http://localhost:6333", validation_alias="QDRANT_URL")
    collection_name: str = Field(default="documents", validation_alias="QDRANT_COLLECTION")
    vector_size: int = Field(default=768, validation_alias="QDRANT_VECTOR_SIZE")


class AuthConfig(BaseSettings):
    """认证配置"""
    jwt_secret: str = Field("test-secret-key-for-testing-only", env="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(15, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(7, env="REFRESH_TOKEN_EXPIRE_DAYS")


class LogConfig(BaseSettings):
    """日志配置"""
    level: str = Field("INFO", env="LOG_LEVEL")
    format: str = Field("json", env="LOG_FORMAT")
    file_path: Optional[str] = Field(None, env="LOG_FILE_PATH")
    max_file_size: int = Field(10 * 1024 * 1024, env="LOG_MAX_FILE_SIZE")  # 10MB
    backup_count: int = Field(5, env="LOG_BACKUP_COUNT")
    elasticsearch_url: Optional[str] = Field(None, env="ELASTICSEARCH_URL")


class SecurityConfig(BaseSettings):
    """安全配置"""
    allowed_origins: List[str] = Field(["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003"], env="ALLOWED_ORIGINS")
    rate_limit_per_minute: int = Field(1000, env="RATE_LIMIT_PER_MINUTE")
    max_file_size: int = Field(50 * 1024 * 1024, env="MAX_FILE_SIZE")  # 50MB
    allowed_file_types: List[str] = Field([
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
        "application/epub+zip",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "text/csv",
        "text/html",
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/bmp",
        "image/gif"
    ], env="ALLOWED_FILE_TYPES")
    login_max_attempts: int = Field(5, env="LOGIN_MAX_ATTEMPTS")
    login_lockout_minutes: int = Field(15, env="LOGIN_LOCKOUT_MINUTES")
    register_rate_limit_per_ip: int = Field(3, env="REGISTER_RATE_LIMIT_PER_IP")
    register_rate_limit_window: int = Field(60, env="REGISTER_RATE_LIMIT_WINDOW")
    csrf_enabled: bool = Field(True, env="CSRF_ENABLED")
    csrf_secret: str = Field("csrf-secret-key-change-in-production", env="CSRF_SECRET")
    internal_api_keys: List[str] = Field([], env="INTERNAL_API_KEYS")
    internal_ip_whitelist: List[str] = Field([], env="INTERNAL_IP_WHITELIST")
    disable_default_admin_login: bool = Field(False, env="DISABLE_DEFAULT_ADMIN_LOGIN")


class CeleryConfig(BaseSettings):
    """Celery配置"""
    broker_url: str = Field("redis://localhost:6379/1", env="CELERY_BROKER_URL")
    result_backend: str = Field("redis://localhost:6379/2", env="CELERY_RESULT_BACKEND")
    task_serializer: str = Field("json", env="CELERY_TASK_SERIALIZER")
    result_serializer: str = Field("json", env="CELERY_RESULT_SERIALIZER")
    worker_concurrency: int = Field(2, env="CELERY_WORKER_CONCURRENCY")


class Settings(BaseSettings):
    """主配置类"""
    
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    
    # 应用配置
    app_name: str = Field("Enterprise RAG System", env="APP_NAME")
    app_version: str = Field("2.2.0rc1", env="APP_VERSION")
    debug: bool = Field(False, env="DEBUG")
    environment: str = Field("development", env="ENVIRONMENT")
    upload_dir: str = Field("./uploads", env="UPLOAD_DIR")
    
    # 数据库配置（直接在主配置中定义）
    database_url: str = Field("sqlite+aiosqlite:///:memory:", env="DATABASE_URL")
    db_pool_size: int = Field(10, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(20, env="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(30, env="DB_POOL_TIMEOUT")
    db_pool_pre_ping: bool = Field(True, env="DB_POOL_PRE_PING")
    db_pool_recycle: int = Field(3600, env="DB_POOL_RECYCLE")
    db_echo: bool = Field(False, env="DB_ECHO")
    
    # Redis配置
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")

    # X OAuth 2.0 PKCE（未配置时授权入口明确返回未配置，不模拟成功）
    x_oauth_client_id: str = Field("", env="X_OAUTH_CLIENT_ID")
    x_oauth_client_secret: str = Field("", env="X_OAUTH_CLIENT_SECRET")
    x_oauth_redirect_uri: str = Field("", env="X_OAUTH_REDIRECT_URI")
    x_oauth_scopes: str = Field("tweet.read tweet.write users.read offline.access", env="X_OAUTH_SCOPES")
    
    # 日志配置（直接在主配置中定义）
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_format: str = Field("json", env="LOG_FORMAT")
    log_file_path: Optional[str] = Field(None, env="LOG_FILE_PATH")
    log_max_file_size: int = Field(10 * 1024 * 1024, env="LOG_MAX_FILE_SIZE")  # 10MB
    log_backup_count: int = Field(5, env="LOG_BACKUP_COUNT")
    log_elasticsearch_url: Optional[str] = Field(None, env="ELASTICSEARCH_URL")
    
    # 子配置（使用主配置的值）
    database: Optional[DatabaseConfig] = None
    redis: Optional[RedisConfig] = None
    qdrant: QdrantConfig = QdrantConfig()
    auth: AuthConfig = AuthConfig()
    log: LogConfig = LogConfig()
    security: SecurityConfig = SecurityConfig()
    celery: CeleryConfig = CeleryConfig()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        db_url = normalize_database_url(self.database_url)
        if db_url != self.database_url:
            object.__setattr__(self, "database_url", db_url)
        # 使用主配置的值初始化子配置
        object.__setattr__(self, 'database', DatabaseConfig(
            url=db_url,
            pool_size=self.db_pool_size,
            max_overflow=self.db_max_overflow,
            pool_timeout=self.db_pool_timeout,
            pool_pre_ping=self.db_pool_pre_ping,
            pool_recycle=self.db_pool_recycle,
            echo=self.db_echo
        ))
        object.__setattr__(self, 'redis', RedisConfig(url=self.redis_url))
        # CeleryConfig 是嵌套 BaseSettings；仅声明 Field(env=...) 不会在主配置
        # 已实例化后可靠重载进程环境变量。显式重建，确保 API 与 Worker 使用同一 broker。
        object.__setattr__(self, 'celery', CeleryConfig(
            broker_url=os.getenv("CELERY_BROKER_URL", self.celery.broker_url),
            result_backend=os.getenv("CELERY_RESULT_BACKEND", self.celery.result_backend),
            task_serializer=os.getenv("CELERY_TASK_SERIALIZER", self.celery.task_serializer),
            result_serializer=os.getenv("CELERY_RESULT_SERIALIZER", self.celery.result_serializer),
            worker_concurrency=int(os.getenv("CELERY_WORKER_CONCURRENCY", self.celery.worker_concurrency)),
        ))
        # 与 database/redis 一致：在进程环境变量就绪后再实例化，避免嵌套 QdrantConfig 停留在默认 localhost
        object.__setattr__(self, 'qdrant', QdrantConfig())
        object.__setattr__(self, 'log', LogConfig(
            level=self.log_level,
            format=self.log_format,
            file_path=self.log_file_path,
            max_file_size=self.log_max_file_size,
            backup_count=self.log_backup_count,
            elasticsearch_url=self.log_elasticsearch_url
        ))

    def validate_production_secrets(self) -> None:
        """
        在非调试且非测试环境阻止弱默认密钥启动。
        """
        if self.debug:
            return
        if str(os.getenv("TESTING", "")).lower() == "true":
            return

        production_like = self.environment.lower() in {"production", "prod", "staging"}

        weak_jwt_secrets = {
            "test-secret-key-for-testing-only",
            "change-this-in-production",
            "change-me-in-production",
            "",
        }
        jwt_secret = (self.auth.jwt_secret or "").strip()
        csrf_secret = (self.security.csrf_secret or "").strip().lower()

        if jwt_secret in weak_jwt_secrets:
            raise ValueError("生产环境禁止使用弱 JWT_SECRET，请设置强随机密钥")

        if not csrf_secret or "change" in csrf_secret or "test" in csrf_secret:
            raise ValueError("生产环境禁止使用弱 CSRF_SECRET，请设置强随机密钥")

        if production_like:
            internal_keys = [
                str(key).strip()
                for key in self.security.internal_api_keys
                if str(key).strip()
            ]
            if not internal_keys or any(
                key.lower() in {"change-me-in-production", "test-staging-key"}
                for key in internal_keys
            ):
                raise ValueError("生产环境必须配置有效 INTERNAL_API_KEYS")
            if not self.security.internal_ip_whitelist:
                raise ValueError("生产环境必须配置 INTERNAL_IP_WHITELIST")


@lru_cache()
def get_settings() -> Settings:
    """获取配置实例（单例）"""
    return Settings()
