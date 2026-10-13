"""Agent 工具注册表与安全执行边界。

工具必须显式注册；运行时不接受 Python 表达式、shell、任意 HTTP 客户端或动态导入。
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from services.impl.safe_fetcher import SafeFetcher


@dataclass(frozen=True)
class AgentTool:
    key: str
    label: str
    description: str
    input_schema: dict[str, Any]
    requires_approval: bool
    read_only: bool = True


class AgentToolRegistry:
    """集中维护 Agent 可调用的最小工具集合。"""

    _tools = (
        AgentTool(
            key="safe_fetch_url",
            label="安全抓取网页",
            description="通过 SafeFetcher 获取用户明确指定的公开 URL，禁止内网与云元数据地址。",
            input_schema={"url": "string", "max_bytes": "integer<=2000000"},
            requires_approval=True,
        ),
        AgentTool(
            key="extract_terms",
            label="提取候选术语",
            description="从已提供的文本中提取候选中英文术语，不访问外部系统。",
            input_schema={"text": "string<=20000"},
            requires_approval=False,
        ),
    )

    def __init__(self, fetcher: SafeFetcher | None = None):
        self.fetcher = fetcher or SafeFetcher(max_bytes=2 * 1024 * 1024)
        self._by_key = {tool.key: tool for tool in self._tools}

    def get(self, key: str) -> AgentTool | None:
        return self._by_key.get(str(key).strip().lower())

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "key": tool.key,
                "label": tool.label,
                "description": tool.description,
                "input_schema": tool.input_schema,
                "requires_approval": tool.requires_approval,
                "read_only": tool.read_only,
            }
            for tool in self._tools
        ]

    async def execute(self, key: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.get(key)
        if tool is None:
            raise ValueError(f"未注册的 Agent 工具: {key}")
        if not isinstance(arguments, dict):
            raise ValueError("Agent 工具参数必须是 JSON 对象")
        if tool.key == "safe_fetch_url":
            url = str(arguments.get("url") or "").strip()
            if not url:
                raise ValueError("safe_fetch_url 缺少 url")
            max_bytes = int(arguments.get("max_bytes") or 2 * 1024 * 1024)
            if not 1 <= max_bytes <= 2 * 1024 * 1024:
                raise ValueError("safe_fetch_url max_bytes 超出允许范围")
            fetched = await SafeFetcher(max_bytes=max_bytes).fetch(url)
            return {
                "tool": tool.key,
                "url": fetched.url,
                "content_type": fetched.content_type,
                "content_hash": hashlib.sha256(fetched.content).hexdigest(),
                "content": fetched.content.decode("utf-8", errors="replace")[:20000],
                "requires_approval": tool.requires_approval,
            }
        if tool.key == "extract_terms":
            text = str(arguments.get("text") or "")
            if not text.strip():
                raise ValueError("extract_terms 缺少 text")
            if len(text) > 20000:
                raise ValueError("extract_terms text 超过 20000 字符")
            terms = re.findall(r"[\u4e00-\u9fff]{2,8}|[A-Za-z][A-Za-z0-9_-]{1,24}", text)
            return {"tool": tool.key, "terms": list(dict.fromkeys(terms))[:100], "requires_approval": False}
        raise RuntimeError(f"工具已注册但没有安全执行器: {tool.key}")
