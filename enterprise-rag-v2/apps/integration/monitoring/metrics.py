"""
监控指标服务

收集和暴露消息网关的监控指标
"""

import prometheus_client
from prometheus_client import Counter, Gauge, Histogram
from typing import Dict, Any

# 定义监控指标

# 请求计数器
REQUEST_COUNT = Counter(
    'integration_request_count',
    'Total number of integration requests',
    ['platform', 'endpoint', 'method', 'status']
)

# 请求处理时间直方图
REQUEST_LATENCY = Histogram(
    'integration_request_latency_seconds',
    'Request latency in seconds',
    ['platform', 'endpoint']
)

# 错误计数器
ERROR_COUNT = Counter(
    'integration_error_count',
    'Total number of errors',
    ['platform', 'error_type']
)

# 活跃会话数
ACTIVE_CONVERSATIONS = Gauge(
    'integration_active_conversations',
    'Number of active conversations',
    ['platform']
)

# 配额使用情况
QUOTA_USAGE = Gauge(
    'integration_quota_usage',
    'Quota usage percentage',
    ['tenant_id', 'dimension']
)

# 用户映射计数器
USER_MAPPING_COUNT = Counter(
    'integration_user_mapping_count',
    'User mapping operations',
    ['operation', 'result']
)


class MetricsService:
    """监控指标服务"""
    
    @staticmethod
    def record_request(platform: str, endpoint: str, method: str, status: int, latency: float):
        """记录请求指标"""
        REQUEST_COUNT.labels(
            platform=platform,
            endpoint=endpoint,
            method=method,
            status=status
        ).inc()
        
        REQUEST_LATENCY.labels(
            platform=platform,
            endpoint=endpoint
        ).observe(latency)
    
    @staticmethod
    def record_error(platform: str, error_type: str):
        """记录错误指标"""
        ERROR_COUNT.labels(
            platform=platform,
            error_type=error_type
        ).inc()
    
    @staticmethod
    def update_active_conversations(platform: str, count: int):
        """更新活跃会话数"""
        ACTIVE_CONVERSATIONS.labels(platform=platform).set(count)
    
    @staticmethod
    def update_quota_usage(tenant_id: str, dimension: str, usage: float):
        """更新配额使用情况"""
        QUOTA_USAGE.labels(
            tenant_id=tenant_id,
            dimension=dimension
        ).set(usage)
    
    @staticmethod
    def record_user_mapping(operation: str, result: str):
        """记录用户映射操作"""
        USER_MAPPING_COUNT.labels(
            operation=operation,
            result=result
        ).inc()
    
    @staticmethod
    def get_metrics() -> str:
        """获取所有指标"""
        return prometheus_client.generate_latest().decode('utf-8')
