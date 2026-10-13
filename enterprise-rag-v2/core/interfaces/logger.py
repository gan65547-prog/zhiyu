"""
日志抽象接口

定义结构化日志系统的抽象接口
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from enum import Enum
from datetime import datetime
from uuid import UUID


class LogLevel(Enum):
    """日志级别"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogEntry:
    """日志条目"""
    
    def __init__(self,
                 timestamp: datetime,
                 level: LogLevel,
                 message: str,
                 module: str,
                 trace_id: Optional[str] = None,
                 user_id: Optional[UUID] = None,
                 tenant_id: Optional[UUID] = None,
                 workspace_id: Optional[UUID] = None,
                 **context):
        self.timestamp = timestamp
        self.level = level
        self.message = message
        self.module = module
        self.trace_id = trace_id
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.workspace_id = workspace_id
        self.context = context


class LogFormatter(ABC):
    """日志格式化器接口"""
    
    @abstractmethod
    def format(self, entry: LogEntry) -> str:
        """格式化日志条目"""
        pass


class LogHandler(ABC):
    """日志处理器接口"""
    
    @abstractmethod
    async def handle(self, formatted_log: str) -> None:
        """处理格式化后的日志"""
        pass


class LogContextManager(ABC):
    """日志上下文管理器接口"""
    
    @abstractmethod
    def get_trace_id(self) -> Optional[str]:
        """获取当前请求的追踪ID"""
        pass
    
    @abstractmethod
    def get_user_id(self) -> Optional[UUID]:
        """获取当前用户ID"""
        pass
    
    @abstractmethod
    def get_tenant_id(self) -> Optional[UUID]:
        """获取当前租户ID"""
        pass
    
    @abstractmethod
    def get_workspace_id(self) -> Optional[UUID]:
        """获取当前工作空间ID"""
        pass
    
    @abstractmethod
    def set_context(self, **context) -> None:
        """设置日志上下文"""
        pass


class StructuredLogger(ABC):
    """结构化日志记录器接口"""
    
    @abstractmethod
    async def debug(self, message: str, **context) -> None:
        """记录DEBUG级别日志"""
        pass
    
    @abstractmethod
    async def info(self, message: str, **context) -> None:
        """记录INFO级别日志"""
        pass
    
    @abstractmethod
    async def warning(self, message: str, **context) -> None:
        """记录WARNING级别日志"""
        pass
    
    @abstractmethod
    async def error(self, message: str, **context) -> None:
        """记录ERROR级别日志"""
        pass
    
    @abstractmethod
    async def critical(self, message: str, **context) -> None:
        """记录CRITICAL级别日志"""
        pass
    
    @abstractmethod
    async def log(self, level: LogLevel, message: str, **context) -> None:
        """记录指定级别的日志"""
        pass