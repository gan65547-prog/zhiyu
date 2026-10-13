#!/usr/bin/env python3
"""测试配置加载"""

import sys
sys.path.insert(0, '/Users/gan/Documents/ganfy/enterprise-rag-v2')

import os
print('CWD:', os.getcwd())
print('.env exists:', os.path.exists('.env'))

from core.config import get_settings
settings = get_settings()
print('Database URL:', settings.database.url)
print('Environment:', settings.environment)
