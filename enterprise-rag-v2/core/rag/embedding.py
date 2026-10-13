"""
Embedding服务实现

提供文本向量化和批量向量化功能
使用sentence-transformers加载BGE模型生成语义向量
"""

from typing import List, Optional
import os
from pathlib import Path
from functools import lru_cache
import threading

import httpx

from core.rag_config import get_rag_config
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Embedding服务基类"""

    def __init__(self, model_name: Optional[str] = None):
        self.config = get_rag_config()
        self.model_name = model_name or self.config.embedding_model

    def embed_text(self, text: str) -> List[float]:
        """单文本向量化"""
        raise NotImplementedError("子类必须实现此方法")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化"""
        raise NotImplementedError("子类必须实现此方法")

    def get_dimension(self) -> int:
        """获取向量维度"""
        return self.config.vector_size

    def close(self):
        """关闭资源"""
        pass


class SentenceTransformerEmbedding(EmbeddingService):
    """
    基于Sentence-Transformers的Embedding实现
    使用BGE等模型生成真正的语义向量
    """

    _model_instance = None
    _model_lock = threading.Lock()
    _runtime_env_ready = False
    _resolved_model_name = None
    _last_used_time = 0
    _model_idle_timeout = 1800
    _max_memory_fraction = 0.5

    def __init__(self, model_name: Optional[str] = None):
        super().__init__(model_name or "BAAI/bge-small-zh-v1.5")
        self._dimension = 512  # bge-small-zh-v1.5 的向量维度

    @classmethod
    def _prepare_runtime_env(cls) -> None:
        """为模型加载准备稳定的缓存/镜像环境。"""
        if cls._runtime_env_ready:
            return

        project_root = Path(__file__).resolve().parents[2]
        cache_root = project_root / ".cache"
        hf_home = cache_root / "huggingface"
        st_home = cache_root / "sentence_transformers"
        hf_home.mkdir(parents=True, exist_ok=True)
        st_home.mkdir(parents=True, exist_ok=True)

        # 仅在未显式配置时设置默认值，避免覆盖用户自定义环境。
        os.environ.setdefault("HF_HOME", str(hf_home))
        os.environ.setdefault("TRANSFORMERS_CACHE", str(hf_home / "transformers"))
        os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(st_home))
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        cls._runtime_env_ready = True

    @staticmethod
    def _model_path_has_weights(model_path: str) -> bool:
        """检查模型路径是否包含有效的权重文件"""
        path = Path(model_path)
        if not path.is_dir():
            return False
        for f in ("model.safetensors", "pytorch_model.bin", "tf_model.h5", "flax_model.msgpack"):
            if (path / f).exists():
                return True
        return False

    def _resolve_model_name(self) -> str:
        """
        优先使用固定路径模型，避免外网依赖。
        解析优先级：
        1) 共享卷路径 /app/shared/models/bge-small-zh-v1.5
        2) EMBEDDING_MODEL_PATH（环境变量/配置）
        3) 镜像预置路径 /opt/models/bge-small-zh-v1.5
        4) 原始模型名（触发 HuggingFace 下载）
        """
        # 1) 共享卷挂载路径
        local_model_path = "/app/shared/models/bge-small-zh-v1.5"
        if self._model_path_has_weights(local_model_path):
            logger.info(f"_resolve_model_name: using local model path: {local_model_path}")
            return local_model_path

        # 2) 环境变量 / 配置路径
        configured_path = (self.config.embedding_model_path or "").strip()
        if configured_path and self._model_path_has_weights(configured_path):
            logger.info(f"_resolve_model_name: using configured_path: {configured_path}")
            return configured_path
        if configured_path:
            logger.info(f"_resolve_model_name: configured_path exists but missing weight files: {configured_path}")

        # 3) 镜像预置路径
        bundled_path = Path("/opt/models/bge-small-zh-v1.5")
        if bundled_path.exists():
            if self._model_path_has_weights(str(bundled_path)):
                logger.info(f"_resolve_model_name: using bundled_path: {bundled_path}")
                return str(bundled_path)
            else:
                logger.warning(f"_resolve_model_name: bundled_path exists but missing weight files, will fallback to download")

        # 4) 最终回退：从 HuggingFace 下载
        logger.info(f"_resolve_model_name: using model_name (will download from HF): {self.model_name}")
        return self.model_name

    def _get_model(self):
        """懒加载模型（单例模式），带内存限制和自动释放"""
        import gc
        import time
        
        current_time = time.time()
        
        if SentenceTransformerEmbedding._model_instance is not None:
            if current_time - SentenceTransformerEmbedding._last_used_time > SentenceTransformerEmbedding._model_idle_timeout:
                logger.info("Embedding模型闲置超时，释放内存")
                del SentenceTransformerEmbedding._model_instance
                SentenceTransformerEmbedding._model_instance = None
                gc.collect()
        
        if SentenceTransformerEmbedding._model_instance is None:
            with SentenceTransformerEmbedding._model_lock:
                if SentenceTransformerEmbedding._model_instance is None:
                    try:
                        SentenceTransformerEmbedding._prepare_runtime_env()
                        from sentence_transformers import SentenceTransformer
                        resolved_model_name = self._resolve_model_name()
                        SentenceTransformerEmbedding._resolved_model_name = resolved_model_name
                        logger.info(f"正在加载Embedding模型: {resolved_model_name}")
                        
                        device = os.getenv("EMBEDDING_DEVICE")
                        
                        if device:
                            SentenceTransformerEmbedding._model_instance = SentenceTransformer(
                                resolved_model_name,
                                device=device,
                            )
                        else:
                            SentenceTransformerEmbedding._model_instance = SentenceTransformer(
                                resolved_model_name,
                                device='cpu',
                            )
                        
                        SentenceTransformerEmbedding._last_used_time = current_time
                        self._dimension = SentenceTransformerEmbedding._model_instance.get_sentence_embedding_dimension()
                        logger.info(f"Embedding模型加载成功，向量维度: {self._dimension}")
                    except (ImportError, OSError, RuntimeError, ValueError, TypeError, AttributeError) as e:
                        logger.error(f"加载Embedding模型失败: {e}")
                        raise
        
        SentenceTransformerEmbedding._last_used_time = current_time
        return SentenceTransformerEmbedding._model_instance

    async def embed_text(self, text: str) -> List[float]:
        """使用Sentence-Transformers进行文本向量化"""
        try:
            model = self._get_model()
            import asyncio
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None,
                lambda: model.encode(text, normalize_embeddings=True).tolist()
            )
            return embedding
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"Embedding错误: {e}")
            raise

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化，使用chunked处理避免内存溢出"""
        try:
            model = self._get_model()
            import asyncio
            loop = asyncio.get_event_loop()
            
            max_batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "32"))
            
            all_embeddings = []
            for i in range(0, len(texts), max_batch_size):
                batch = texts[i:i + max_batch_size]
                embeddings = await loop.run_in_executor(
                    None,
                    lambda b=batch: model.encode(b, normalize_embeddings=True, show_progress_bar=False).tolist()
                )
                all_embeddings.extend(embeddings)
            
            return all_embeddings
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"批量Embedding错误: {e}")
            raise

    def get_dimension(self) -> int:
        """获取向量维度"""
        return self._dimension

    @classmethod
    def close(cls):
        """释放 Embedding 模型内存，在应用关闭时调用"""
        import gc
        if cls._model_instance is not None:
            logger.info("关闭 Embedding 模型并释放内存")
            del cls._model_instance
            cls._model_instance = None
            cls._resolved_model_name = None
            cls._last_used_time = 0
            gc.collect()


class BGESmallZhEmbedding(SentenceTransformerEmbedding):
    """
    BGE-small-zh-v1.5 Embedding实现
    
    特点：
    - 中文语义向量模型
    - 向量维度: 512
    - 适合中文文本检索任务
    - 支持批量处理，性能优秀
    """

    def __init__(self):
        super().__init__("BAAI/bge-small-zh-v1.5")
        self._dimension = 512


class BGELargeZhEmbedding(SentenceTransformerEmbedding):
    """
    BGE-large-zh-v1.5 Embedding实现
    
    特点：
    - 中文语义向量模型（大模型版本）
    - 向量维度: 1024
    - 更高的语义理解能力
    - 需要更多内存和计算资源
    """

    def __init__(self):
        super().__init__("BAAI/bge-large-zh-v1.5")
        self._dimension = 1024


class OllamaEmbedding(EmbeddingService):
    """Ollama Embedding实现"""

    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__(model_name or "nomic-embed-text")
        self.base_url = base_url or "http://localhost:11434"
        self._dimension = 768

    async def embed_text(self, text: str) -> List[float]:
        """使用Ollama进行文本向量化"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={
                        "model": self.model_name,
                        "prompt": text
                    }
                )
                response.raise_for_status()
                result = response.json()
                embedding = result.get("embedding", [])
                if embedding:
                    self._dimension = len(embedding)
                return embedding
            except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.error(f"Ollama Embedding错误: {e}")
                raise

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化"""
        return [await self.embed_text(text) for text in texts]

    def get_dimension(self) -> int:
        return self._dimension


class DeepSeekEmbedding(SentenceTransformerEmbedding):
    """
    DeepSeek Embedding实现
    
    注意：DeepSeek目前不提供独立的Embedding API
    使用BGE模型作为替代方案，提供高质量的中文语义向量
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        super().__init__("BAAI/bge-small-zh-v1.5")
        self.api_key = api_key or self.config.deepseek_api_key
        self._dimension = 512
        logger.info(f"Embedding服务: 使用BGE-small-zh-v1.5模型（向量维度: {self._dimension}）")


def get_embedding_service(model_name: Optional[str] = None) -> EmbeddingService:
    """
    获取Embedding服务实例
    
    Args:
        model_name: 模型名称，支持:
            - "bge-small-zh": BGE-small-zh-v1.5 (默认，512维)
            - "bge-large-zh": BGE-large-zh-v1.5 (1024维)
            - "nomic-embed-text": Ollama的nomic模型
    
    Returns:
        EmbeddingService实例
    """
    if model_name is None:
        model_name = "bge-small-zh"
    
    model_name_lower = model_name.lower()
    
    if "bge-small" in model_name_lower or model_name_lower == "bge-small-zh":
        return BGESmallZhEmbedding()
    elif "bge-large" in model_name_lower or model_name_lower == "bge-large-zh":
        return BGELargeZhEmbedding()
    elif "nomic" in model_name_lower or "ollama" in model_name_lower:
        return OllamaEmbedding(model_name)
    else:
        return SentenceTransformerEmbedding(model_name)
