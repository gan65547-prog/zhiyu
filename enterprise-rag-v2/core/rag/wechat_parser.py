"""
微信聊天记录解析器

支持 WeChatMsg 等工具导出的 TXT、CSV 格式。
将聊天记录转换为适合 RAG 检索的结构化文本。
"""

import csv
import io
import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ChatMessage:
    """单条聊天消息"""
    timestamp: str = ""
    sender: str = ""
    content: str = ""
    msg_type: str = "text"


@dataclass
class ParseResult:
    """解析结果"""
    messages: List[ChatMessage] = field(default_factory=list)
    format_detected: str = ""
    total_messages: int = 0
    participants: List[str] = field(default_factory=list)
    date_range: tuple = ()
    errors: List[str] = field(default_factory=list)


class WechatChatParser:
    """微信聊天记录解析器"""

    # 常见时间格式
    TIMESTAMP_PATTERNS = [
        re.compile(r'^(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2}:\d{2})\s+(\S+?)\s*$'),
        re.compile(r'^(\d{4}/\d{2}/\d{2}\s+\d{1,2}:\d{2}:\d{2})\s+(\S+?)\s*$'),
        re.compile(r'^(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})\s+(\S+?)\s*$'),
        re.compile(r'^(\d{2,4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2}:\d{2})\s+(\S+?)\s*$'),
    ]

    # CSV 列名映射（各种导出工具的差异）
    CSV_COLUMN_MAPS = [
        {"timestamp": ["timestamp", "time", "时间", "日期时间", "datetime", "create_time", "created_at"]},
        {"sender": ["sender", "name", "user", "username", "发送者", "发言人", "from", "author", "nickname", "talker"]},
        {"content": ["content", "message", "msg", "text", "内容", "消息", "body", "str_content"]},
        {"msg_type": ["msg_type", "type", "message_type", "类型", "mime_type"]},
    ]

    def parse(self, file_path: str) -> ParseResult:
        """自动检测格式并解析聊天记录文件"""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return self.parse_content(content)

    def parse_content(self, content: str) -> ParseResult:
        """解析聊天记录文本内容"""
        if not content or not content.strip():
            result = ParseResult()
            result.errors.append("文件内容为空")
            return result

        content = content.strip()

        # 尝试 CSV
        if content.lstrip().startswith("{") or self._looks_like_csv(content):
            try:
                return self._parse_csv(content)
            except Exception:
                pass

        # 默认 TXT 格式
        return self._parse_txt(content)

    def _looks_like_csv(self, content: str) -> bool:
        """检测是否为 CSV 格式"""
        first_line = content.split("\n")[0].strip().lower()
        csv_indicators = ["timestamp", "sender", "时间", "发送者", "content", "message"]
        return any(indicator in first_line for indicator in csv_indicators)

    def _detect_csv_columns(self, headers: List[str]) -> dict:
        """自动映射 CSV 列名"""
        mapping = {"timestamp": None, "sender": None, "content": None, "msg_type": None}
        headers_lower = [h.strip().lower() for h in headers]

        for col_group in self.CSV_COLUMN_MAPS:
            for key, aliases in col_group.items():
                for alias in aliases:
                    if alias in headers_lower:
                        idx = headers_lower.index(alias)
                        mapping[key] = idx
                        break
                if mapping[key] is not None:
                    break

        return mapping

    def _parse_csv(self, content: str) -> ParseResult:
        """解析 CSV 格式"""
        result = ParseResult(format_detected="csv")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        if not rows:
            result.errors.append("CSV 文件无数据")
            return result

        # 第一行可能是表头
        col_map = self._detect_csv_columns(rows[0])
        start_row = 1 if any(v is not None for v in col_map.values()) else 0

        if start_row == 0:
            col_map = {"timestamp": 0, "sender": 1, "content": 2, "msg_type": 3}

        participants = set()

        for row in rows[start_row:]:
            if not row or all(c.strip() == "" for c in row):
                continue

            try:
                msg = ChatMessage()
                if col_map["timestamp"] is not None and col_map["timestamp"] < len(row):
                    msg.timestamp = row[col_map["timestamp"]].strip()
                if col_map["sender"] is not None and col_map["sender"] < len(row):
                    msg.sender = row[col_map["sender"]].strip()
                if col_map["content"] is not None and col_map["content"] < len(row):
                    msg.content = row[col_map["content"]].strip()
                if col_map["msg_type"] is not None and col_map["msg_type"] < len(row):
                    msg.msg_type = row[col_map["msg_type"]].strip()

                if msg.content:
                    result.messages.append(msg)
                    if msg.sender:
                        participants.add(msg.sender)
            except (IndexError, ValueError):
                continue

        result.participants = list(participants)
        result.total_messages = len(result.messages)
        return result

    def _parse_txt(self, content: str) -> ParseResult:
        """解析 TXT 格式（WeChatMsg 默认导出格式）

        格式示例:
            2024-01-15 14:30:25 张三
            这是消息内容
            可能多行

            2024-01-15 14:31:10 李四
            回复消息
        """
        result = ParseResult(format_detected="txt")
        lines = content.split("\n")
        participants = set()

        current_msg = None
        content_lines = []

        def flush_message():
            nonlocal current_msg, content_lines
            if current_msg is not None:
                current_msg.content = "\n".join(content_lines).strip()
                if current_msg.content:
                    result.messages.append(current_msg)
                    if current_msg.sender:
                        participants.add(current_msg.sender)
            current_msg = None
            content_lines = []

        for line in lines:
            match = None
            for pattern in self.TIMESTAMP_PATTERNS:
                match = pattern.match(line.strip())
                if match:
                    break

            if match:
                flush_message()
                groups = match.groups()
                if len(groups) == 2:
                    timestamp, sender = groups
                elif len(groups) == 3:
                    timestamp = f"{groups[0]} {groups[1]}"
                    sender = groups[2]
                else:
                    continue

                current_msg = ChatMessage(timestamp=timestamp.strip(), sender=sender.strip())
                content_lines = []
            elif current_msg is not None:
                if line.strip():
                    content_lines.append(line.strip())
                elif content_lines:
                    content_lines.append("")

        flush_message()

        result.participants = list(participants)
        result.total_messages = len(result.messages)

        if result.total_messages == 0:
            result.errors.append("未能从文件中解析出聊天消息，请确认文件格式")

        if result.messages:
            timestamps = [m.timestamp for m in result.messages if m.timestamp]
            if timestamps:
                result.date_range = (timestamps[0], timestamps[-1])

        return result

    def to_searchable_text(self, result: ParseResult) -> str:
        """将解析结果转换为适合 RAG 检索的文本格式

        每条消息格式: [时间] 发送者: 内容
        便于全文检索和 AI 理解上下文
        """
        lines = []
        for msg in result.messages:
            parts = []
            if msg.timestamp:
                parts.append(f"[{msg.timestamp}]")
            if msg.sender:
                parts.append(f" {msg.sender}:")
            else:
                parts.append(" ")
            parts.append(f" {msg.content}")
            lines.append("".join(parts))

        return "\n".join(lines)

    def to_document_text(self, result: ParseResult, chat_name: str = "") -> str:
        """生成适合创建文档的完整文本，带元数据头"""
        header_parts = []

        if chat_name:
            header_parts.append(f"聊天对象: {chat_name}")
        if result.participants:
            header_parts.append(f"参与人: {', '.join(result.participants)}")
        if result.date_range and result.date_range[0]:
            header_parts.append(f"时间范围: {result.date_range[0]}")
            if result.date_range[1]:
                header_parts[-1] += f" 至 {result.date_range[1]}"
        header_parts.append(f"消息总数: {result.total_messages}")
        header_parts.append("\n" + "=" * 50 + "\n")

        header = "\n".join(header_parts)
        body = self.to_searchable_text(result)

        return header + body
