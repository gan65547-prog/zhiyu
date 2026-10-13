from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ops-center"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8081
    app_debug: bool = True

    business_base_url: str = "http://host.docker.internal:8000"
    internal_api_key: str = ""
    source_env: str = "ops-center-staging"
    request_timeout_seconds: float = 10.0
    gateway_read_retry_count: int = 1
    gateway_read_retry_backoff_seconds: float = 0.2
    read_cache_ttl_seconds: int = 300
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_window_seconds: int = 60
    circuit_breaker_open_seconds: int = 60
    auth_secret_key: str = Field(min_length=32)
    auth_token_expire_seconds: int = 3600
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = Field(min_length=12)
    bootstrap_admin_roles: str = "super_admin"
    ops_db_path: str = "./.data/ops_center.db"
    # 非空时使用 PostgreSQL（psycopg），为空时回退 SQLite（ops_db_path）
    ops_database_url: str = ""

    @field_validator("auth_secret_key")
    @classmethod
    def validate_auth_secret_key(cls, value: str) -> str:
        if value.lower().startswith(("change-me", "replace-", "your-", "placeholder")):
            raise ValueError("AUTH_SECRET_KEY must be replaced with a unique secret")
        return value

    @field_validator("bootstrap_admin_password")
    @classmethod
    def validate_bootstrap_admin_password(cls, value: str) -> str:
        if value.lower().startswith(("change-me", "replace-", "your-", "placeholder")):
            raise ValueError("BOOTSTRAP_ADMIN_PASSWORD must be replaced with a unique password")
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
