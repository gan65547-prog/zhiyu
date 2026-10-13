"""
分页相关值对象
"""

from typing import List, Any


class Pagination:
    """分页参数"""
    
    def __init__(self, page: int = 1, page_size: int = 20):
        if page < 1:
            raise ValueError("Page must be >= 1")
        if page_size < 1 or page_size > 1000:
            raise ValueError("Page size must be between 1 and 1000")
        self.page = page
        self.page_size = page_size
    
    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        """获取限制数量"""
        return self.page_size


class Page:
    """分页结果 - 不使用泛型避免FastAPI序列化问题"""
    
    def __init__(self, items: List[Any], total: int, page: int, page_size: int):
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size
    
    @property
    def total_pages(self) -> int:
        """总页数"""
        return (self.total + self.page_size - 1) // self.page_size if self.page_size > 0 else 0
    
    @property
    def has_next(self) -> bool:
        """是否有下一页"""
        return self.page < self.total_pages
    
    @property
    def has_prev(self) -> bool:
        """是否有上一页"""
        return self.page > 1
