"""
核心异常类
"""


class ResourceNotFoundError(Exception):
    """资源未找到异常"""
    pass


class PermissionDeniedError(Exception):
    """权限拒绝异常"""
    pass


class BusinessError(Exception):
    """业务逻辑异常"""
    pass


class ValidationError(Exception):
    """验证异常"""
    pass


class ResourceConflictError(Exception):
    """资源冲突异常"""
    pass


class QuotaExceededError(Exception):
    """通用配额超限异常"""

    def __init__(self, resource_type: str, current: int, limit: int):
        self.resource_type = resource_type
        self.current = current
        self.limit = limit
        super().__init__(f"配额超限: {resource_type} 当前 {current}, 限制 {limit}")
