"""
RAG引擎配置

定义RAG引擎的配置参数
"""

import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RAGConfig(BaseSettings):
    """RAG引擎配置"""
    
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    
    qdrant_url: str = Field("http://localhost:6333", env="QDRANT_URL")
    collection_name: str = Field("documents", env="QDRANT_COLLECTION")
    vector_size: int = Field(512, env="QDRANT_VECTOR_SIZE")  # BGE-small-zh-v1.5 embedding维度
    
    # DeepSeek API配置 (使用OpenAI兼容格式)
    deepseek_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    deepseek_base_url: str = Field("https://api.deepseek.com/v1", env="OPENAI_BASE_URL")
    deepseek_model: str = Field("deepseek-chat", env="OPENAI_MODEL")
    deepseek_embedding_model: str = Field("deepseek-embedding", env="EMBEDDING_MODEL")
    
    # 本地模型配置（备用）
    embedding_model: str = Field("sentence-transformers/all-MiniLM-L6-v2", env="EMBEDDING_MODEL")
    embedding_model_path: Optional[str] = Field(None, env="EMBEDDING_MODEL_PATH")
    rerank_model: str = Field("cross-encoder/ms-marco-MiniLM-L-6-v2", env="RERANK_MODEL")
    llm_model: str = Field("llama2", env="LLM_MODEL")
    llm_url: str = Field("http://localhost:11434", env="OLLAMA_URL")
    # 生产部署默认走 OpenAI 兼容接口；本地 Ollama 仍可通过显式 LLM_PROVIDER=ollama 启用。
    llm_provider: str = Field("deepseek", env="LLM_PROVIDER")
    
    # 其他配置
    default_top_k: int = Field(8, env="DEFAULT_TOP_K")
    default_similarity_threshold: float = Field(0.45, env="DEFAULT_SIMILARITY_THRESHOLD")
    max_context_chunks: int = Field(10, env="MAX_CONTEXT_CHUNKS")
    enable_rerank: bool = Field(True, env="ENABLE_RERANK")


def normalize_openai_base_url(url: str) -> str:
    """
    OpenAI 兼容接口的 base URL，必须以 /v1 结尾，否则 /chat/completions 会 404。
    常见误配：https://api.deepseek.com（缺 /v1）→ 自动补全。
    """
    u = (url or "").strip().rstrip("/")
    if not u:
        return "https://api.deepseek.com/v1"
    if not u.endswith("/v1"):
        u = f"{u}/v1"
    return u


def is_effective_openai_api_key(key: Optional[str]) -> bool:
    """
    判断 OPENAI_API_KEY 是否为可用的远端密钥。
    占位符（如仓库自带 sk-test-key-for-development）视为无效，便于本地自动回退 Ollama。
    """
    if not key:
        return False
    s = str(key).strip()
    lower = s.lower()
    placeholders = {
        "sk-test-key-for-development",
        "sk-test",
        "changeme",
        "your-api-key-here",
        "replace-with-your-key",
    }
    if lower in placeholders:
        return False
    # 不再对长度做硬编码限制：
    # 不同厂商/不同发放阶段的兼容密钥长度可能不同（例如 35 位），
    # 仅排除空值和常见占位符，避免误判有效密钥。
    return True


# 全局配置实例
_rag_config: Optional[RAGConfig] = None


def get_rag_config() -> RAGConfig:
    """获取RAG配置（单例模式）"""
    global _rag_config
    if _rag_config is None:
        _rag_config = RAGConfig()
        # 运行时兜底：某些部署环境下 BaseSettings 对 env 映射可能失效，
        # 若字段仍为空，则直接从进程环境回填，避免误回退到 Ollama。
        if not (_rag_config.deepseek_api_key or "").strip():
            # DEEPSEEK_API_KEY 是部署侧更不易与通用 OPENAI_API_KEY 混淆的别名；
            # 仍保留 OPENAI_API_KEY 以兼容所有 OpenAI-compatible provider。
            env_key = (
                os.getenv("OPENAI_API_KEY", "").strip()
                or os.getenv("DEEPSEEK_API_KEY", "").strip()
            )
            if env_key:
                _rag_config.deepseek_api_key = env_key
        # BaseSettings 在不同部署方式下对 Field(env=...) 的兼容行为不一致；
        # 对模型运行时关键字段显式读取进程环境，避免容器继续使用默认 provider/地址。
        env_overrides = {
            "deepseek_base_url": "OPENAI_BASE_URL",
            "deepseek_model": "OPENAI_MODEL",
            "llm_provider": "LLM_PROVIDER",
            "llm_model": "LLM_MODEL",
            "llm_url": "OLLAMA_URL",
        }
        for field_name, env_name in env_overrides.items():
            value = os.getenv(env_name, "").strip()
            if value:
                setattr(_rag_config, field_name, value)
        if not os.getenv("LLM_PROVIDER", "").strip() and is_effective_openai_api_key(_rag_config.deepseek_api_key):
            _rag_config.llm_provider = "deepseek"
        # 对embedding_model_path进行环境变量兜底处理
        if not (_rag_config.embedding_model_path or "").strip():
            env_path = os.getenv("EMBEDDING_MODEL_PATH", "").strip()
            if env_path:
                _rag_config.embedding_model_path = env_path
    return _rag_config
