"""
指标收集器

提供系统指标收集功能
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timedelta
import asyncio


@dataclass
class Metric:
    """指标数据"""
    name: str
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._start_time = time.time()

    def increment(self, name: str, value: float = 1.0, labels: Dict[str, str] = None) -> None:
        """增加计数器"""
        key = self._make_key(name, labels)
        self._counters[key] += value

    def set_gauge(self, name: str, value: float, labels: Dict[str, str] = None) -> None:
        """设置计量器"""
        key = self._make_key(name, labels)
        self._gauges[key] = value

    def observe_histogram(self, name: str, value: float, labels: Dict[str, str] = None) -> None:
        """记录直方图"""
        key = self._make_key(name, labels)
        self._histograms[key].append(value)

        if len(self._histograms[key]) > 1000:
            self._histograms[key] = self._histograms[key][-1000:]

    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        """生成键名"""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_counter(self, name: str, labels: Dict[str, str] = None) -> float:
        """获取计数器值"""
        key = self._make_key(name, labels)
        return self._counters.get(key, 0.0)

    def get_gauge(self, name: str, labels: Dict[str, str] = None) -> Optional[float]:
        """获取计量器值"""
        key = self._make_key(name, labels)
        return self._gauges.get(key)

    def get_histogram_stats(self, name: str, labels: Dict[str, str] = None) -> Dict[str, float]:
        """获取直方图统计"""
        key = self._make_key(name, labels)
        values = self._histograms.get(key, [])

        if not values:
            return {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}

        sorted_values = sorted(values)
        count = len(sorted_values)

        return {
            "count": count,
            "sum": sum(sorted_values),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "avg": sum(sorted_values) / count,
            "p50": sorted_values[int(count * 0.5)],
            "p95": sorted_values[int(count * 0.95)] if count >= 20 else sorted_values[-1],
            "p99": sorted_values[int(count * 0.99)] if count >= 100 else sorted_values[-1],
        }

    def get_all_metrics(self) -> Dict[str, Any]:
        """获取所有指标"""
        return {
            "uptime_seconds": time.time() - self._start_time,
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                name: self.get_histogram_stats(name)
                for name in self._histograms.keys()
            }
        }

    def reset(self) -> None:
        """重置所有指标"""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


class RequestMetrics:
    """请求指标中间件辅助类"""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector

    def record_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float
    ) -> None:
        """记录请求指标"""
        labels = {
            "method": method,
            "path": path,
            "status_code": str(status_code)
        }

        self.collector.increment("http_requests_total", 1.0, labels)
        self.collector.observe_histogram("http_request_duration_ms", duration_ms, labels)

        if status_code >= 500:
            self.collector.increment("http_errors_total", 1.0, labels)
        elif status_code >= 400:
            self.collector.increment("http_client_errors_total", 1.0, labels)

    def record_rag_query(self, duration_ms: float, num_docs: int) -> None:
        """记录RAG查询指标"""
        self.collector.increment("rag_queries_total")
        self.collector.observe_histogram("rag_query_duration_ms", duration_ms)
        self.collector.observe_histogram("rag_retrieved_docs", float(num_docs))

    def record_database_query(self, duration_ms: float, operation: str) -> None:
        """记录数据库查询指标"""
        labels = {"operation": operation}
        self.collector.increment("db_queries_total", 1.0, labels)
        self.collector.observe_histogram("db_query_duration_ms", duration_ms, labels)

    def record_quota_exceeded(self, dimension: str, tenant_id: str) -> None:
        """记录配额超限指标"""
        labels = {"dimension": dimension}
        self.collector.increment("quota_exceeded_total", 1.0, labels)

    def record_api_call(self, endpoint: str, status: str, duration_ms: float) -> None:
        """记录API调用指标"""
        labels = {"endpoint": endpoint, "status": status}
        self.collector.increment("api_calls_total", 1.0, labels)
        self.collector.observe_histogram("api_call_duration_ms", duration_ms, labels)


_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """获取指标收集器实例"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
