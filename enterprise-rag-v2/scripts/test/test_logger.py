#!/usr/bin/env python3
"""测试日志系统"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from infrastructure.logging.logger import (
    LoggerFactory,
    JSONLogFormatter,
    FileLogHandler,
    ConsoleLogHandler,
    get_logger
)

print("Testing logger...")

# 测试 FileLogHandler
log_path = os.path.join(os.path.dirname(__file__), "logs", "app.log")
print(f"Log path: {log_path}")

# 手动创建目录
log_dir = os.path.dirname(log_path)
os.makedirs(log_dir, exist_ok=True)

# 测试写入
file_handler = FileLogHandler(log_path, JSONLogFormatter())
console_handler = ConsoleLogHandler(JSONLogFormatter())

LoggerFactory._default_handlers = [file_handler, console_handler]

logger = get_logger("test")

print("Writing test logs...")
logger.info("Test info message", test="value")
logger.warning("Test warning message", key="test")
logger.error("Test error message", error="test")

print(f"Checking log file: {log_path}")
if os.path.exists(log_path):
    print(f"✅ Log file created! Size: {os.path.getsize(log_path)} bytes")
    with open(log_path, 'r') as f:
        print("Log content:")
        print(f.read())
else:
    print("❌ Log file not created!")
