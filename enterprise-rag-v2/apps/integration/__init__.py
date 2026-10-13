"""
集成模块 - OpenClaw混合架构

负责处理来自OpenClaw消息网关的请求，
提供统一的聊天、用户绑定、健康检查等接口。

架构:
  OpenClaw (Node.js) → HTTP API → FastAPI (Python) → RAG 与资源治理

主要功能:
  - POST /api/v1/integration/chat      (核心: 知识库查询 + 配额检查)
  - POST /api/v1/integration/bind       (用户绑定)
  - GET  /api/v1/integration/health     (健康检查)
"""

__version__ = "2.0.0-hybrid"
