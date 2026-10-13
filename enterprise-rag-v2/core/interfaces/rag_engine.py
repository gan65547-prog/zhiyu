"""
RAG引擎抽象接口

定义RAG系统核心组件的抽象接口
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class RetrievedDocument:
    """检索到的文档"""
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float
    document_id: str
    document_name: str
    chunk_index: int


@dataclass
class QueryContext:
    """查询上下文"""
    workspace_id: UUID
    dataset_ids: Optional[List[UUID]] = None
    top_k: int = 5
    similarity_threshold: float = 0.5
    retrieval_mode: str = "hybrid"  # semantic, keyword, hybrid
    rerank: bool = True


@dataclass
class RAGResponse:
    """RAG响应"""
    answer: str
    retrieved_documents: List[RetrievedDocument]
    tokens_used: int
    retrieval_time_ms: int
    generation_time_ms: int
    metadata: Dict[str, Any]


class DocumentRetriever(ABC):
    """文档检索器抽象接口"""
    
    @abstractmethod
    async def retrieve(
        self, 
        query: str, 
        context: QueryContext
    ) -> List[RetrievedDocument]:
        """
        检索相关文档
        
        Args:
            query: 用户查询
            context: 查询上下文
            
        Returns:
            检索到的文档列表
        """
        pass
    
    @abstractmethod
    async def semantic_search(
        self,
        query_embedding: List[float],
        context: QueryContext
    ) -> List[RetrievedDocument]:
        """
        语义检索
        
        Args:
            query_embedding: 查询向量
            context: 查询上下文
            
        Returns:
            检索到的文档列表
        """
        pass
    
    @abstractmethod
    async def keyword_search(
        self,
        query: str,
        context: QueryContext
    ) -> List[RetrievedDocument]:
        """
        关键词检索
        
        Args:
            query: 用户查询
            context: 查询上下文
            
        Returns:
            检索到的文档列表
        """
        pass


class DocumentReranker(ABC):
    """文档重排序器抽象接口"""
    
    @abstractmethod
    async def rerank(
        self, 
        query: str, 
        documents: List[RetrievedDocument]
    ) -> List[RetrievedDocument]:
        """
        重排序文档
        
        Args:
            query: 用户查询
            documents: 待排序的文档列表
            
        Returns:
            重排序后的文档列表
        """
        pass


class ResponseGenerator(ABC):
    """响应生成器抽象接口"""
    
    @abstractmethod
    async def generate(
        self, 
        query: str, 
        documents: List[RetrievedDocument],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """
        生成回答
        
        Args:
            query: 用户查询
            documents: 检索到的文档
            conversation_history: 对话历史
            temperature: 生成温度
            max_tokens: 最大token数
            
        Returns:
            生成的回答
        """
        pass
    
    @abstractmethod
    async def generate_stream(
        self,
        query: str,
        documents: List[RetrievedDocument],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        """
        流式生成回答
        
        Args:
            query: 用户查询
            documents: 检索到的文档
            conversation_history: 对话历史
            temperature: 生成温度
            max_tokens: 最大token数
            
        Yields:
            生成的文本片段
        """
        pass


class EmbeddingProvider(ABC):
    """嵌入模型提供商抽象接口"""
    
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """
        文本向量化
        
        Args:
            text: 输入文本
            
        Returns:
            向量表示
        """
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量文本向量化
        
        Args:
            texts: 输入文本列表
            
        Returns:
            向量列表
        """
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """
        获取向量维度
        
        Returns:
            向量维度
        """
        pass


class DocumentProcessor(ABC):
    """文档处理器抽象接口"""
    
    @abstractmethod
    async def extract_text(self, file_path: str, file_type: str) -> str:
        """
        提取文档文本
        
        Args:
            file_path: 文件路径
            file_type: 文件类型
            
        Returns:
            提取的文本
        """
        pass
    
    @abstractmethod
    def supports(self, file_type: str) -> bool:
        """
        检查是否支持该文件类型
        
        Args:
            file_type: 文件类型
            
        Returns:
            是否支持
        """
        pass


class TextSplitter(ABC):
    """文本分块器抽象接口"""
    
    @abstractmethod
    def split(
        self, 
        text: str, 
        chunk_size: int = 500, 
        chunk_overlap: int = 50
    ) -> List[str]:
        """
        分割文本
        
        Args:
            text: 输入文本
            chunk_size: 块大小
            chunk_overlap: 块重叠
            
        Returns:
            文本块列表
        """
        pass


class RAGEngine(ABC):
    """RAG引擎抽象接口"""
    
    @abstractmethod
    async def query(
        self,
        query: str,
        context: QueryContext,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> RAGResponse:
        """
        执行RAG查询
        
        Args:
            query: 用户查询
            context: 查询上下文
            conversation_history: 对话历史
            temperature: 生成温度
            max_tokens: 最大token数
            
        Returns:
            RAG响应
        """
        pass
    
    @abstractmethod
    async def query_stream(
        self,
        query: str,
        context: QueryContext,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ):
        """
        流式执行RAG查询
        
        Args:
            query: 用户查询
            context: 查询上下文
            conversation_history: 对话历史
            temperature: 生成温度
            max_tokens: 最大token数
            
        Yields:
            响应片段
        """
        pass
