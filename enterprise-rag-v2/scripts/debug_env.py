#!/usr/bin/env python3
"""
调试环境变量
"""

import os
import dotenv

print("当前工作目录:", os.getcwd())
print("ENCRYPTION_KEY 环境变量:", os.getenv("ENCRYPTION_KEY"))

# 尝试加载 .env
dotenv.load_dotenv()
print("加载 .env 后 ENCRYPTION_KEY:", os.getenv("ENCRYPTION_KEY"))

# 检查 .env 文件内容
if os.path.exists(".env"):
    print("\n.env 文件内容:")
    with open(".env", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                print(line)