from typing import Dict


# 自托管部署默认不限制租户资源。运维人员可通过内部控制面设置配额覆盖。
UNLIMITED_QUOTAS: Dict[str, int] = {
    "users": -1,
    "documents": -1,
    "storage_mb": -1,
    "api_calls_monthly": -1,
    "chat_messages_monthly": -1,
    "workspaces": -1,
    "research_runs_monthly": -1,
    "research_sources_monthly": -1,
    "research_output_tokens_monthly": -1,
}


def get_quota_limit() -> Dict[str, int]:
    """返回默认无限资源配额。"""
    return dict(UNLIMITED_QUOTAS)


REDIS_KEYS = {"quota_prefix": "quota:"}


def build_quota_key(tenant_id: str) -> str:
    """构建租户用量 Redis key。"""
    return f"{REDIS_KEYS['quota_prefix']}{tenant_id}"
