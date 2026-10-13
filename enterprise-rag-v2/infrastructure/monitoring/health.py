"""
健康检查器

提供系统组件健康状态检查功能
"""

import asyncio
import os
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

import httpx

from core.config import get_settings
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class HealthStatus(str, Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """组件健康状态"""
    name: str
    status: HealthStatus
    message: Optional[str] = None
    latency_ms: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class HealthChecker:
    """健康检查器"""

    def __init__(self):
        self.settings = get_settings()
        self._components: Dict[str, callable] = {}
        self.component_timeout_seconds = float(os.getenv("HEALTH_CHECK_TIMEOUT_SECONDS", "5"))

    def register_component(self, name: str, checker: callable) -> None:
        """注册组件检查器"""
        self._components[name] = checker

    async def check_all(self) -> Dict[str, Any]:
        """检查所有组件"""
        results = []
        overall_status = HealthStatus.HEALTHY

        for name, checker in self._components.items():
            try:
                result = await asyncio.wait_for(checker(), timeout=self.component_timeout_seconds)
                if isinstance(result, ComponentHealth):
                    results.append(result)
                    if result.status == HealthStatus.UNHEALTHY:
                        overall_status = HealthStatus.UNHEALTHY
                    elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                        overall_status = HealthStatus.DEGRADED
                else:
                    results.append(ComponentHealth(
                        name=name,
                        status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                    ))
            except asyncio.TimeoutError:
                logger.warning("Health check component timed out: %s", name)
                results.append(ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"健康检查超时（>{self.component_timeout_seconds:g}s）",
                ))
                overall_status = HealthStatus.UNHEALTHY
            except Exception as e:
                logger.warning("Health check component failed: %s error=%s", name, e, exc_info=True)
                results.append(ComponentHealth(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e)
                ))
                overall_status = HealthStatus.UNHEALTHY

        return {
            "status": overall_status.value,
            "timestamp": time.time(),
            "components": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "latency_ms": r.latency_ms,
                    "details": r.details
                }
                for r in results
            ]
        }

    async def check_database(self) -> ComponentHealth:
        """检查数据库连接"""
        start = time.time()
        try:
            from infrastructure.database.session import engine
            from sqlalchemy import text

            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

            return ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY,
                latency_ms=int((time.time() - start) * 1000)
            )
        except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=int((time.time() - start) * 1000)
            )

    async def check_redis(self) -> ComponentHealth:
        """检查Redis连接"""
        start = time.time()
        try:
            from infrastructure.cache import get_cache

            cache = await get_cache()
            await cache.set("health_check", "ok", ttl=10)
            value = await cache.get("health_check")

            if value == "ok":
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.HEALTHY,
                    latency_ms=int((time.time() - start) * 1000)
                )
            else:
                return ComponentHealth(
                    name="redis",
                    status=HealthStatus.DEGRADED,
                    message="Cache read/write mismatch",
                    latency_ms=int((time.time() - start) * 1000)
                )
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=int((time.time() - start) * 1000)
            )

    async def check_qdrant(self) -> ComponentHealth:
        """检查Qdrant向量数据库"""
        start = time.time()
        url = (self.settings.qdrant.url or "").strip()
        if url.startswith("http"):
            try:
                from qdrant_client import QdrantClient

                client = QdrantClient(url=url, check_compatibility=False)
                # qdrant-client 的该调用是同步 I/O；放入线程，才能让 check_all 的
                # asyncio.wait_for 真正限制健康接口的响应时间。
                collections = await asyncio.to_thread(client.get_collections)
                return ComponentHealth(
                    name="qdrant",
                    status=HealthStatus.HEALTHY,
                    latency_ms=int((time.time() - start) * 1000),
                    details={
                        "mode": "http",
                        "collections": len(collections.collections),
                    },
                )
            except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
                return ComponentHealth(
                    name="qdrant",
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                    latency_ms=int((time.time() - start) * 1000),
                )

        try:
            qdrant_data_path = "./qdrant_data"
            if os.path.exists(qdrant_data_path):
                collections_path = os.path.join(qdrant_data_path, "collections")
                if os.path.exists(collections_path):
                    collections = os.listdir(collections_path)
                    return ComponentHealth(
                        name="qdrant",
                        status=HealthStatus.HEALTHY,
                        latency_ms=int((time.time() - start) * 1000),
                        details={"mode": "embedded", "collections": len(collections)}
                    )

            from qdrant_client import QdrantClient
            client = QdrantClient(path=qdrant_data_path)
            collections = client.get_collections()
            return ComponentHealth(
                name="qdrant",
                status=HealthStatus.HEALTHY,
                latency_ms=int((time.time() - start) * 1000),
                details={"mode": "embedded", "collections": len(collections.collections)}
            )
        except (ImportError, OSError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            return ComponentHealth(
                name="qdrant",
                status=HealthStatus.DEGRADED,
                message=f"Embedded mode: {str(e)}",
                latency_ms=int((time.time() - start) * 1000)
            )

    async def check_llm(self) -> ComponentHealth:
        """检查当前配置的 LLM provider，而不是固定探测 Ollama。"""
        start = time.time()
        try:
            from core.rag_config import get_rag_config, is_effective_openai_api_key, normalize_openai_base_url

            config = get_rag_config()
            provider = str(config.llm_provider or "ollama").strip().lower()

            if provider == "ollama":
                endpoint = f"{str(config.llm_url).rstrip('/')}/api/tags"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(endpoint)
                if response.status_code == 200:
                    return ComponentHealth(
                        name="llm",
                        status=HealthStatus.HEALTHY,
                        latency_ms=int((time.time() - start) * 1000),
                        details={"provider": provider, "model": config.llm_model},
                    )
                return ComponentHealth(
                    name="llm",
                    status=HealthStatus.DEGRADED,
                    message=f"{provider} status code: {response.status_code}",
                    latency_ms=int((time.time() - start) * 1000),
                    details={"provider": provider, "model": config.llm_model},
                )

            if provider not in {"openai", "deepseek"}:
                return ComponentHealth(
                    name="llm",
                    status=HealthStatus.DEGRADED,
                    message=f"Unsupported LLM provider: {provider}",
                    latency_ms=int((time.time() - start) * 1000),
                )

            if not is_effective_openai_api_key(config.deepseek_api_key):
                return ComponentHealth(
                    name="llm",
                    status=HealthStatus.DEGRADED,
                    message=f"{provider} API key not configured",
                    latency_ms=int((time.time() - start) * 1000)
                )

            base_url = normalize_openai_base_url(config.deepseek_base_url)
            # 健康检查只探测鉴权和服务可达性，不消耗一次模型生成额度。
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers={
                        "Authorization": f"Bearer {config.deepseek_api_key}"
                    }
                )

                if response.status_code == 200:
                    return ComponentHealth(
                        name="llm",
                        status=HealthStatus.HEALTHY,
                        latency_ms=int((time.time() - start) * 1000),
                        details={"provider": provider, "model": config.deepseek_model}
                    )
                else:
                    return ComponentHealth(
                        name="llm",
                        status=HealthStatus.DEGRADED,
                        message=f"{provider} status code: {response.status_code}",
                        latency_ms=int((time.time() - start) * 1000),
                        details={"provider": provider, "model": config.deepseek_model},
                    )
        except httpx.TimeoutException:
            return ComponentHealth(
                name="llm",
                status=HealthStatus.DEGRADED,
                message=f"{provider} health probe timed out",
                latency_ms=int((time.time() - start) * 1000),
                details={"provider": provider},
            )
        except (httpx.HTTPError, ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            return ComponentHealth(
                name="llm",
                status=HealthStatus.DEGRADED,
                message=str(e),
                latency_ms=int((time.time() - start) * 1000)
            )


_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """获取健康检查器实例"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
        _health_checker.register_component("database", _health_checker.check_database)
        _health_checker.register_component("redis", _health_checker.check_redis)
        _health_checker.register_component("qdrant", _health_checker.check_qdrant)
        _health_checker.register_component("llm", _health_checker.check_llm)
    return _health_checker
