"""
RAG诊断工具

提供向量数据库连接诊断、集合状态检查等功能
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from enum import Enum

import httpx

from core.rag_config import get_rag_config
from core.rag.vector_store import VectorStore, QdrantVectorStore
from core.rag.collection_manager import CollectionManager
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class DiagnosticStatus(str, Enum):
    """诊断状态"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    WARNING = "warning"
    ERROR = "error"


class RAGDiagnosticTool:
    """RAG诊断工具"""
    
    def __init__(self):
        self.config = get_rag_config()
        self.results: List[Dict[str, Any]] = []
    
    async def run_full_diagnostic(self) -> Dict[str, Any]:
        """
        运行完整诊断
        
        Returns:
            Dict: 诊断结果
        """
        self.results = []
        
        logger.info("Starting full RAG diagnostic...")
        
        checks = [
            ("environment", self._check_environment),
            ("vector_db_connection", self._check_vector_db_connection),
            ("collection_status", self._check_collection_status),
            ("embedding_service", self._check_embedding_service),
            ("llm_service", self._check_llm_service),
        ]
        
        for check_name, check_func in checks:
            try:
                result = await check_func()
                self.results.append({
                    "name": check_name,
                    "status": result.get("status", DiagnosticStatus.ERROR),
                    "message": result.get("message", ""),
                    "details": result.get("details", {}),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.exception("Diagnostic check '%s' failed: %s", check_name, e)
                self.results.append({
                    "name": check_name,
                    "status": DiagnosticStatus.ERROR,
                    "message": str(e),
                    "details": {},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        
        overall_status = self._calculate_overall_status()
        
        return {
            "overall_status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": self.results,
            "summary": self._generate_summary()
        }
    
    async def _check_environment(self) -> Dict[str, Any]:
        """检查环境配置"""
        issues = []
        
        required_vars = [
            "QDRANT_URL",
            "EMBEDDING_MODEL",
            "LLM_PROVIDER"
        ]
        
        import os
        for var in required_vars:
            if not os.getenv(var):
                issues.append(f"Missing environment variable: {var}")
        
        if issues:
            return {
                "status": DiagnosticStatus.WARNING,
                "message": "Some environment variables are not set",
                "details": {"issues": issues}
            }
        
        return {
            "status": DiagnosticStatus.HEALTHY,
            "message": "All required environment variables are set",
            "details": {}
        }
    
    async def _check_vector_db_connection(self) -> Dict[str, Any]:
        """检查向量数据库连接"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.config.qdrant_url}/collections")
                
                if response.status_code == 200:
                    collections = response.json().get("result", {}).get("collections", [])
                    return {
                        "status": DiagnosticStatus.HEALTHY,
                        "message": "Vector database connection successful",
                        "details": {
                            "collections_count": len(collections),
                            "url": self.config.qdrant_url
                        }
                    }
                else:
                    return {
                        "status": DiagnosticStatus.UNHEALTHY,
                        "message": f"Vector database returned status {response.status_code}",
                        "details": {}
                    }
        except (httpx.HTTPError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            return {
                "status": DiagnosticStatus.ERROR,
                "message": f"Failed to connect to vector database: {str(e)}",
                "details": {"url": self.config.qdrant_url}
            }
    
    async def _check_collection_status(self) -> Dict[str, Any]:
        """检查集合状态"""
        try:
            manager = await CollectionManager.get_instance()
            info = await manager.get_collection_info()
            
            if info.get("exists"):
                return {
                    "status": DiagnosticStatus.HEALTHY,
                    "message": f"Collection '{info.get('name')}' exists and ready",
                    "details": info
                }
            else:
                return {
                    "status": DiagnosticStatus.WARNING,
                    "message": f"Collection '{info.get('name')}' does not exist",
                    "details": info
                }
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            return {
                "status": DiagnosticStatus.ERROR,
                "message": f"Failed to check collection status: {str(e)}",
                "details": {}
            }
    
    async def _check_embedding_service(self) -> Dict[str, Any]:
        """检查嵌入服务"""
        try:
            from core.rag.embedding import EmbeddingService
            
            embedding_service = EmbeddingService()
            
            test_text = "This is a test sentence for embedding."
            vector = await embedding_service.embed_text(test_text)
            
            if vector and len(vector) > 0:
                return {
                    "status": DiagnosticStatus.HEALTHY,
                    "message": "Embedding service is working",
                    "details": {
                        "vector_dimension": len(vector),
                        "model": self.config.embedding_model
                    }
                }
            else:
                return {
                    "status": DiagnosticStatus.UNHEALTHY,
                    "message": "Embedding service returned empty vector",
                    "details": {}
                }
        except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            return {
                "status": DiagnosticStatus.ERROR,
                "message": f"Embedding service check failed: {str(e)}",
                "details": {}
            }
    
    async def _check_llm_service(self) -> Dict[str, Any]:
        """检查LLM服务"""
        try:
            from core.rag.llm_provider import LLMProviderFactory
            
            provider = LLMProviderFactory.create(self.config.llm_provider)
            
            return {
                "status": DiagnosticStatus.HEALTHY,
                "message": f"LLM provider '{self.config.llm_provider}' is configured",
                "details": {
                    "provider": self.config.llm_provider,
                    "model": getattr(self.config, 'llm_model', 'default')
                }
            }
        except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            return {
                "status": DiagnosticStatus.WARNING,
                "message": f"LLM service check skipped: {str(e)}",
                "details": {}
            }
    
    def _calculate_overall_status(self) -> str:
        """计算整体状态"""
        if not self.results:
            return DiagnosticStatus.ERROR
        
        statuses = [r["status"] for r in self.results]
        
        if DiagnosticStatus.ERROR in statuses:
            return DiagnosticStatus.ERROR
        elif DiagnosticStatus.UNHEALTHY in statuses:
            return DiagnosticStatus.UNHEALTHY
        elif DiagnosticStatus.WARNING in statuses:
            return DiagnosticStatus.WARNING
        else:
            return DiagnosticStatus.HEALTHY
    
    def _generate_summary(self) -> str:
        """生成诊断摘要"""
        healthy_count = sum(1 for r in self.results if r["status"] == DiagnosticStatus.HEALTHY)
        total_count = len(self.results)
        
        return f"{healthy_count}/{total_count} checks passed"


async def diagnose_rag_system() -> Dict[str, Any]:
    """
    诊断RAG系统
    
    Returns:
        Dict: 诊断结果
    """
    tool = RAGDiagnosticTool()
    return await tool.run_full_diagnostic()


def print_diagnostic_report(result: Dict[str, Any]) -> None:
    """打印诊断报告"""
    print("\n" + "=" * 60)
    print("RAG System Diagnostic Report")
    print("=" * 60)
    print(f"Overall Status: {result['overall_status'].upper()}")
    print(f"Timestamp: {result['timestamp']}")
    print(f"Summary: {result['summary']}")
    print("-" * 60)
    
    for check in result["checks"]:
        status_icon = {
            DiagnosticStatus.HEALTHY: "✅",
            DiagnosticStatus.WARNING: "⚠️",
            DiagnosticStatus.UNHEALTHY: "❌",
            DiagnosticStatus.ERROR: "🔴"
        }.get(check["status"], "❓")
        
        print(f"\n{status_icon} {check['name']}")
        print(f"   Status: {check['status']}")
        print(f"   Message: {check['message']}")
        
        if check["details"]:
            print("   Details:")
            for key, value in check["details"].items():
                print(f"     - {key}: {value}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    result = asyncio.run(diagnose_rag_system())
    print_diagnostic_report(result)
