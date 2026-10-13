"""
结构化日志实现

提供JSON格式的结构化日志记录功能
"""

import json
import uuid
import traceback
import os
import logging as _logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from contextvars import ContextVar
from uuid import UUID
from logging.handlers import RotatingFileHandler as _RotatingFileHandler

from core.interfaces.logger import (
    LogLevel,
    LogEntry,
    LogFormatter,
    LogHandler,
    LogContextManager,
    StructuredLogger
)


trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar('tenant_id', default=None)
workspace_id_var: ContextVar[Optional[str]] = ContextVar('workspace_id', default=None)


class JSONLogFormatter(LogFormatter):
    """JSON格式日志格式化器"""

    def format(self, entry: LogEntry) -> str:
        """格式化日志条目为JSON字符串"""
        log_dict = {
            "timestamp": entry.timestamp.isoformat(),
            "level": entry.level.value,
            "message": entry.message,
            "module": entry.module,
            "trace_id": entry.trace_id,
            "user_id": str(entry.user_id) if entry.user_id else None,
            "tenant_id": str(entry.tenant_id) if entry.tenant_id else None,
            "workspace_id": str(entry.workspace_id) if entry.workspace_id else None,
        }

        if entry.context:
            log_dict["context"] = entry.context

        return json.dumps(log_dict, ensure_ascii=False)


class ConsoleLogHandler(LogHandler):
    """控制台日志处理器"""

    def __init__(self, formatter: LogFormatter):
        self.formatter = formatter

    def handle(self, formatted_log: str) -> None:
        """输出到控制台"""
        print(formatted_log)


class FileLogHandler(LogHandler):
    """文件日志处理器（支持轮转）"""

    def __init__(
        self,
        file_path: str,
        formatter: LogFormatter,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ):
        self.file_path = file_path
        self.formatter = formatter
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        self._rotating = _RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )

    def handle(self, formatted_log: str) -> None:
        """写入文件并按大小自动轮转"""
        try:
            sentinel = _logging.LogRecord(
                name="",
                level=_logging.INFO,
                pathname="",
                lineno=0,
                msg=formatted_log,
                args=(),
                exc_info=None,
            )
            if self._rotating.shouldRollover(sentinel):
                self._rotating.doRollover()
            self._rotating.stream.write(formatted_log + "\n")
            self._rotating.stream.flush()
        except Exception as e:
            print(f"Failed to write log: {e}")


class StandardLibJSONHandler(_logging.Handler):
    """将标准库 logging 输出重定向到 JSON 文件（含轮转）"""

    def __init__(
        self,
        file_path: str,
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ):
        super().__init__()
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        self._rotating = _RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )

    def emit(self, record: _logging.LogRecord) -> None:
        try:
            log_dict = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.name,
                "trace_id": None,
                "user_id": None,
                "tenant_id": None,
                "workspace_id": None,
            }
            line = json.dumps(log_dict, ensure_ascii=False)
            sentinel = _logging.LogRecord(
                name=record.name,
                level=record.levelno,
                pathname=record.pathname,
                lineno=record.lineno,
                msg=line,
                args=(),
                exc_info=None,
            )
            if self._rotating.shouldRollover(sentinel):
                self._rotating.doRollover()
            self._rotating.stream.write(line + "\n")
            self._rotating.stream.flush()
        except Exception:
            self.handleError(record)


class LogContextManagerImpl(LogContextManager):
    """日志上下文管理器实现"""

    def get_trace_id(self) -> Optional[str]:
        """获取当前请求的追踪ID"""
        return trace_id_var.get()

    def get_user_id(self) -> Optional[UUID]:
        """获取当前用户ID"""
        user_id = user_id_var.get()
        return UUID(user_id) if user_id else None

    def get_tenant_id(self) -> Optional[UUID]:
        """获取当前租户ID"""
        tenant_id = tenant_id_var.get()
        return UUID(tenant_id) if tenant_id else None

    def get_workspace_id(self) -> Optional[UUID]:
        """获取当前工作空间ID"""
        workspace_id = workspace_id_var.get()
        return UUID(workspace_id) if workspace_id else None

    def set_context(
        self,
        trace_id: Optional[str] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None
    ) -> None:
        """设置日志上下文"""
        if trace_id:
            trace_id_var.set(trace_id)
        if user_id:
            user_id_var.set(user_id)
        if tenant_id:
            tenant_id_var.set(tenant_id)
        if workspace_id:
            workspace_id_var.set(workspace_id)

    def clear(self) -> None:
        """清除上下文"""
        trace_id_var.set(None)
        user_id_var.set(None)
        tenant_id_var.set(None)
        workspace_id_var.set(None)


class StructuredLoggerImpl(StructuredLogger):
    """结构化日志记录器实现"""

    def __init__(
        self,
        handlers: list,
        context_manager: LogContextManager,
        formatter: LogFormatter = None,
        min_level: LogLevel = LogLevel.INFO
    ):
        self._handlers = handlers
        self.context_manager = context_manager
        self.formatter = formatter or JSONLogFormatter()
        self.min_level = min_level
    
    @property
    def handlers(self):
        return self._handlers
    
    @handlers.setter
    def handlers(self, value):
        self._handlers = value

    def _format_message(self, message: str, *args) -> str:
        """兼容标准 logging 的 %s 占位符写法。"""
        if not args:
            return message
        try:
            return message % args
        except Exception:
            # 兜底，避免日志格式化异常影响主流程
            return f"{message} {' '.join(str(a) for a in args)}"

    def debug(self, message: str, *args, **context) -> None:
        """记录DEBUG级别日志"""
        self.log(LogLevel.DEBUG, self._format_message(message, *args), **context)

    def info(self, message: str, *args, **context) -> None:
        """记录INFO级别日志"""
        self.log(LogLevel.INFO, self._format_message(message, *args), **context)

    def warning(self, message: str, *args, **context) -> None:
        """记录WARNING级别日志"""
        self.log(LogLevel.WARNING, self._format_message(message, *args), **context)

    def error(self, message: str, *args, **context) -> None:
        """记录ERROR级别日志"""
        self.log(LogLevel.ERROR, self._format_message(message, *args), **context)

    def critical(self, message: str, *args, **context) -> None:
        """记录CRITICAL级别日志"""
        self.log(LogLevel.CRITICAL, self._format_message(message, *args), **context)

    def exception(self, message: str, *args, **context) -> None:
        """记录异常日志（兼容 logging.exception）。"""
        context.setdefault("traceback", traceback.format_exc())
        self.log(LogLevel.ERROR, self._format_message(message, *args), **context)

    def log(self, level: LogLevel, message: str, **context) -> None:
        """记录指定级别的日志"""
        if level.value not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            return

        if self._level_to_int(level) < self._level_to_int(self.min_level):
            return

        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            level=level,
            message=message,
            module=context.pop("__module__", "unknown"),
            trace_id=self.context_manager.get_trace_id() or str(uuid.uuid4()),
            user_id=self.context_manager.get_user_id(),
            tenant_id=self.context_manager.get_tenant_id(),
            workspace_id=self.context_manager.get_workspace_id(),
            **context
        )

        formatted_log = self.formatter.format(entry)

        for handler in self._handlers:
            try:
                handler.handle(formatted_log)
            except Exception as e:
                print(f"Failed to handle log: {e}")

    def _level_to_int(self, level: LogLevel) -> int:
        """将日志级别转换为整数"""
        level_map = {
            LogLevel.DEBUG: 10,
            LogLevel.INFO: 20,
            LogLevel.WARNING: 30,
            LogLevel.ERROR: 40,
            LogLevel.CRITICAL: 50
        }
        return level_map.get(level, 0)


class LoggerFactory:
    """日志记录器工厂"""

    _loggers: Dict[str, StructuredLogger] = {}
    _default_handlers: list = []
    _global_min_level: LogLevel = LogLevel.INFO

    @classmethod
    def set_global_level(cls, level: LogLevel) -> None:
        """设置全局日志级别并同步已创建实例"""
        cls._global_min_level = level
        for logger in cls._loggers.values():
            logger.min_level = level

    @classmethod
    def get_logger(
        cls,
        name: str,
        handlers: list = None,
        min_level: LogLevel = None
    ) -> StructuredLogger:
        """获取日志记录器"""
        if name in cls._loggers:
            logger = cls._loggers[name]
            if not logger._handlers:
                logger._handlers = cls._default_handlers.copy()
            return logger

        if handlers is None:
            handlers = cls._default_handlers.copy()

        context_manager = LogContextManagerImpl()
        logger = StructuredLoggerImpl(
            handlers=handlers,
            context_manager=context_manager,
            min_level=min_level if min_level is not None else cls._global_min_level
        )

        cls._loggers[name] = logger
        return logger
    
    @classmethod
    def refresh_handlers(cls):
        """刷新所有已创建 logger 的处理器"""
        for logger in cls._loggers.values():
            logger._handlers = cls._default_handlers.copy()


def get_logger(name: str) -> StructuredLogger:
    """获取日志记录器的便捷函数"""
    return LoggerFactory.get_logger(name)


def set_log_context(
    trace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    workspace_id: Optional[str] = None
) -> None:
    """设置日志上下文的便捷函数"""
    context_manager = LogContextManagerImpl()
    context_manager.set_context(
        trace_id=trace_id,
        user_id=user_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id
    )


def clear_log_context() -> None:
    """清除日志上下文"""
    context_manager = LogContextManagerImpl()
    context_manager.clear()
