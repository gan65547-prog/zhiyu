#!/usr/bin/env python
"""
测试运行脚本

在运行测试前设置环境变量
"""

import os
import subprocess
import sys
from pathlib import Path

env_file = Path(__file__).parent / "tests" / ".env.test"

if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest"] + sys.argv[1:], cwd=Path(__file__).parent))
