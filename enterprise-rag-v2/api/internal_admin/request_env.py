"""内部运维路由共用：从头解析目标环境等。"""

from fastapi import Request

from core.config import get_settings


def resolve_target_env(request: Request) -> str:
    """
    优先使用 X-Source-Env（运维中心网关传入），否则回落到 settings.environment。
    兼容单元测试里使用无 headers 的简易 request 替身。
    """
    headers = getattr(request, "headers", None)
    if headers is not None and callable(getattr(headers, "get", None)):
        source_env = (headers.get("X-Source-Env") or "").strip()
        if source_env:
            return source_env
    return get_settings().environment
