"""
监控指标服务

收集和暴露系统性能指标，支持Prometheus格式
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class MetricType(str, Enum):
    """指标类型"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class Metric:
    """指标数据"""
    name: str
    metric_type: MetricType
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    description: str = ""


class MetricsCollector:
    """指标收集器"""
    
    _instance: Optional['MetricsCollector'] = None
    
    def __init__(self):
        self._metrics: Dict[str, Metric] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._lock = asyncio.Lock()
    
    @classmethod
    def get_instance(cls) -> 'MetricsCollector':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def counter(self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """
        递增计数器
        
        Args:
            name: 指标名称
            value: 递增值
            labels: 标签
        """
        key = self._make_key(name, labels or {})
        
        if key in self._metrics:
            self._metrics[key].value += value
        else:
            self._metrics[key] = Metric(
                name=name,
                metric_type=MetricType.COUNTER,
                value=value,
                labels=labels or {}
            )
    
    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        设置仪表值
        
        Args:
            name: 指标名称
            value: 当前值
            labels: 标签
        """
        key = self._make_key(name, labels or {})
        
        self._metrics[key] = Metric(
            name=name,
            metric_type=MetricType.GAUGE,
            value=value,
            labels=labels or {}
        )
    
    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        记录直方图值
        
        Args:
            name: 指标名称
            value: 观测值
            labels: 标签
        """
        key = self._make_key(name, labels or {})
        
        if key not in self._histograms:
            self._histograms[key] = []
        
        self._histograms[key].append(value)
        
        self._metrics[key] = Metric(
            name=name,
            metric_type=MetricType.HISTOGRAM,
            value=value,
            labels=labels or {}
        )
    
    def _make_key(self, name: str, labels: Dict[str, str]) -> str:
        """生成指标键"""
        if not labels:
            return name
        
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
    
    def get_metric(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[Metric]:
        """获取指标"""
        key = self._make_key(name, labels or {})
        return self._metrics.get(key)
    
    def get_all_metrics(self) -> List[Metric]:
        """获取所有指标"""
        return list(self._metrics.values())
    
    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """获取直方图统计"""
        key = self._make_key(name, labels or {})
        
        if key not in self._histograms:
            return {}
        
        values = self._histograms[key]
        
        if not values:
            return {}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            "count": n,
            "sum": sum(values),
            "avg": sum(values) / n,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "p50": sorted_values[int(n * 0.5)],
            "p90": sorted_values[int(n * 0.9)],
            "p95": sorted_values[int(n * 0.95)],
            "p99": sorted_values[int(n * 0.99)]
        }
    
    def to_prometheus_format(self) -> str:
        """转换为Prometheus格式"""
        lines = []
        
        for metric in self._metrics.values():
            labels_str = ""
            if metric.labels:
                labels_str = "{" + ",".join(f'{k}="{v}"' for k, v in metric.labels.items()) + "}"
            
            lines.append(f"# TYPE {metric.name} {metric.metric_type.value}")
            if metric.description:
                lines.append(f"# HELP {metric.name} {metric.description}")
            
            lines.append(f"{metric.name}{labels_str} {metric.value}")
        
        return "\n".join(lines)
    
    def reset(self) -> None:
        """重置所有指标"""
        self._metrics.clear()
        self._histograms.clear()


class TimerContext:
    """计时器上下文管理器"""
    
    def __init__(self, collector: MetricsCollector, name: str, labels: Optional[Dict[str, str]] = None):
        self._collector = collector
        self._name = name
        self._labels = labels
        self._start_time: Optional[float] = None
    
    def __enter__(self):
        self._start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._start_time is not None:
            elapsed = time.time() - self._start_time
            self._collector.histogram(self._name, elapsed, self._labels)
        return False


def timer(name: str, labels: Optional[Dict[str, str]] = None):
    """
    计时器装饰器
    
    Args:
        name: 指标名称
        labels: 标签
    """
    collector = MetricsCollector.get_instance()
    
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            with TimerContext(collector, name, labels):
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            with TimerContext(collector, name, labels):
                return func(*args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class RAGMetrics:
    """RAG系统指标"""
    
    def __init__(self, collector: Optional[MetricsCollector] = None):
        self._collector = collector or MetricsCollector.get_instance()
    
    def record_query(self, success: bool, duration: float, dataset_id: str) -> None:
        """记录查询指标"""
        self._collector.counter(
            "rag_queries_total",
            labels={"dataset": dataset_id, "status": "success" if success else "failed"}
        )
        self._collector.histogram(
            "rag_query_duration_seconds",
            duration,
            labels={"dataset": dataset_id}
        )
    
    def record_document_upload(self, success: bool, file_size: int, duration: float) -> None:
        """记录文档上传指标"""
        self._collector.counter(
            "document_uploads_total",
            labels={"status": "success" if success else "failed"}
        )
        self._collector.histogram(
            "document_upload_size_bytes",
            file_size
        )
        self._collector.histogram(
            "document_upload_duration_seconds",
            duration
        )
    
    def record_indexing(self, success: bool, chunk_count: int, duration: float) -> None:
        """记录索引指标"""
        self._collector.counter(
            "document_indexing_total",
            labels={"status": "success" if success else "failed"}
        )
        self._collector.histogram(
            "document_indexing_chunks",
            chunk_count
        )
        self._collector.histogram(
            "document_indexing_duration_seconds",
            duration
        )
    
    def record_embedding_generation(self, count: int, duration: float) -> None:
        """记录嵌入生成指标"""
        self._collector.counter("embeddings_generated_total", count)
        self._collector.histogram("embedding_generation_duration_seconds", duration)
    
    def record_cache_hit(self, cache_type: str) -> None:
        """记录缓存命中"""
        self._collector.counter(
            "cache_hits_total",
            labels={"type": cache_type}
        )
    
    def record_cache_miss(self, cache_type: str) -> None:
        """记录缓存未命中"""
        self._collector.counter(
            "cache_misses_total",
            labels={"type": cache_type}
        )
    
    def set_active_connections(self, count: int) -> None:
        """设置活跃连接数"""
        self._collector.gauge("active_connections", count)
    
    def set_vector_db_size(self, size: int) -> None:
        """设置向量数据库大小"""
        self._collector.gauge("vector_db_size", size)


def get_metrics() -> str:
    """获取Prometheus格式的指标"""
    collector = MetricsCollector.get_instance()
    return collector.to_prometheus_format()


def get_metrics_json() -> Dict[str, Any]:
    """获取JSON格式的指标"""
    collector = MetricsCollector.get_instance()
    
    metrics = []
    for metric in collector.get_all_metrics():
        metrics.append({
            "name": metric.name,
            "type": metric.metric_type.value,
            "value": metric.value,
            "labels": metric.labels,
            "timestamp": metric.timestamp
        })
    
    return {
        "metrics": metrics,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
