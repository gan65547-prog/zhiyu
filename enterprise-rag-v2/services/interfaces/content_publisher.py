"""内容发布端口：内容域不依赖任何具体平台 SDK。"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ConnectorResult:
    status: str
    response: dict[str, Any]
    external_id: str | None = None


class ContentPublisher(Protocol):
    key: str
    label: str

    async def dispatch(self, *, draft: Any, record: Any, credentials: dict[str, Any] | None = None) -> ConnectorResult:
        """执行一次受控发布尝试。"""
