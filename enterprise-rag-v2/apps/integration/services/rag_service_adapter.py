"""
RAG服务适配器 - 将QueryService与真实RAG引擎桥接

QueryService期望rag_service.search()接口，而真实RAG实现在ChatServiceImpl中。
这个适配器桥接两者之间的接口差异。
"""

from typing import Optional, Dict, Any, List
from uuid import UUID

from apps.integration.models.response import SourceInfo
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class RAGServiceAdapter:
    """
    RAG服务适配器

    将QueryService期望的rag_service接口适配到ChatServiceImpl
    """

    def __init__(self, db=None, tenant_id: Optional[str] = None):
        self.db = db
        self.tenant_id = tenant_id
        logger.info(f"[RAGAdapter] 初始化: db类型={type(db)}, tenant_id={tenant_id}")

    async def search(
        self,
        query: str,
        dataset_id: Optional[UUID],
        dataset_ids: Optional[List[UUID]],
        user_id: int,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行RAG知识库检索

        Args:
            query: 查询文本
            dataset_id: 单个数据集ID（兼容）
            dataset_ids: 数据集ID列表（优先）
            user_id: 用户ID
            conversation_id: 会话ID

        Returns:
            包含answer和sources的字典
        """
        logger.info(
            f"[RAGAdapter] search方法被调用: dataset_id={dataset_id}, "
            f"dataset_ids_count={len(dataset_ids or [])}"
        )

        if not dataset_id and not dataset_ids:
            logger.warning("[RAGAdapter] dataset_id为空，尝试租户级回退选库")
            fallback_dataset_id = await self._resolve_dataset_by_tenant()
            if not fallback_dataset_id:
                logger.warning("[RAGAdapter] 租户级回退选库失败，无法执行RAG搜索")
                return self._empty_result(conversation_id, "抱歉，未找到相关知识库或您无权访问。")
            dataset_id = fallback_dataset_id
            dataset_ids = [UUID(str(fallback_dataset_id))]
            logger.info(f"[RAGAdapter] 租户级回退选库成功: dataset_id={dataset_id}")

        try:
            # 检查ChatServiceImpl是否存在
            try:
                from services.impl.chat_service import ChatServiceImpl
                logger.info("[RAGAdapter] 成功导入ChatServiceImpl")
            except ImportError as e:
                logger.error(f"[RAGAdapter] 导入ChatServiceImpl失败: {e}")
                return self._empty_result(
                    conversation_id,
                    "抱歉，系统暂时无法处理您的请求，请稍后再试。"
                )

            # 确保使用正确的数据库会话
            try:
                from infrastructure.database.session import AsyncSessionLocal
                logger.info("[RAGAdapter] 成功导入AsyncSessionLocal")
                
                # 创建一个新的数据库会话
                async with AsyncSessionLocal() as session:
                    logger.info("[RAGAdapter] 成功创建数据库会话")
                    
                    logger.info(
                        f"[RAGAdapter] 开始RAG搜索: query={query[:50]}, dataset_id={dataset_id}, "
                        f"user_id={user_id}, tenant_id={self.tenant_id}"
                    )

                    try:
                        chat_svc = ChatServiceImpl(session)
                        logger.info("[RAGAdapter] 成功创建ChatServiceImpl实例")
                    except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                        logger.error(f"[RAGAdapter] 创建ChatServiceImpl实例失败: {e}")
                        return self._empty_result(
                            conversation_id,
                            "抱歉，系统暂时无法处理您的请求，请稍后再试。"
                        )

                    # 转换dataset_id为UUID
                    try:
                        from uuid import UUID as UUIDType
                        dataset_uuid = UUIDType(str(dataset_id)) if dataset_id else None
                        logger.info(f"[RAGAdapter] 转换dataset_id为UUID成功: {dataset_uuid}")
                    except (ValueError, TypeError) as e:
                        logger.error(f"[RAGAdapter] 转换dataset_id为UUID失败: {e}")
                        return self._empty_result(
                            conversation_id,
                            "抱歉，系统暂时无法处理您的请求，请稍后再试。"
                        )

                    # 转换conversation_id为UUID
                    try:
                        from uuid import UUID as UUIDType
                        conversation_uuid = UUIDType(conversation_id) if conversation_id else None
                        logger.info(f"[RAGAdapter] 转换conversation_id为UUID成功: {conversation_uuid}")
                    except (ValueError, TypeError) as e:
                        logger.error(f"[RAGAdapter] 转换conversation_id为UUID失败: {e}")
                        conversation_uuid = None

                    dataset_uuid_list = []
                    if dataset_ids:
                        dataset_uuid_list = [UUIDType(str(item)) for item in dataset_ids]

                    logger.info(
                        f"[RAGAdapter] 调用chat_svc.chat: dataset_uuid={dataset_uuid}, "
                        f"dataset_uuid_list_count={len(dataset_uuid_list)}"
                    )

                    # 调用chat_svc.chat
                    try:
                        result = await chat_svc.chat(
                            dataset_id=dataset_uuid,
                            dataset_ids=dataset_uuid_list if dataset_uuid_list else None,
                            query=query,
                            conversation_id=conversation_uuid,
                            user_id=str(user_id),
                            tenant_id=self.tenant_id
                        )
                        logger.info(f"[RAGAdapter] 调用chat_svc.chat成功，结果类型: {type(result)}")
                    except (RuntimeError, ValueError, TypeError, AttributeError, PermissionError) as e:
                        logger.error(f"[RAGAdapter] 调用chat_svc.chat失败: {e}", exc_info=True)
                        return self._empty_result(
                            conversation_id,
                            "抱歉，系统暂时无法处理您的请求，请稍后再试。"
                        )

                    logger.info(
                        f"[RAGAdapter] RAG搜索完成: answer_length={len(result.get('answer', ''))}, "
                        f"docs_count={len(result.get('retrieved_documents', []))}"
                    )

                    sources = []
                    for doc in result.get("retrieved_documents", []):
                        sources.append(SourceInfo(
                            document_title=doc.get("metadata", {}).get("title", "未知文档"),
                            dataset_name="知识库",
                            relevance_score=doc.get("score", 0),
                            content_snippet=doc.get("content", "")[:200]
                        ))

                    return {
                        "answer": result.get("answer", ""),
                        "sources": sources,
                        "conversation_id": result.get("conversation_id")
                    }
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.error(f"[RAGAdapter] 创建数据库会话失败: {e}", exc_info=True)
                return self._empty_result(
                    conversation_id,
                    "抱歉，系统暂时无法处理您的请求，请稍后再试。"
                )

        except ValueError as e:
            logger.warning(f"[RAGAdapter] 数据集不存在或UUID转换失败: {e}")
            return self._empty_result(conversation_id, "抱歉，未找到相关知识库或您无权访问。")

        except PermissionError as e:
            logger.warning(f"[RAGAdapter] 权限不足: {e}")
            return self._empty_result(conversation_id, "抱歉，您没有权限访问该知识库。")

        except (RuntimeError, TypeError, AttributeError) as e:
            logger.error(f"[RAGAdapter] RAG搜索异常: {e}", exc_info=True)
            return self._empty_result(
                conversation_id,
                "抱歉，系统暂时无法处理您的请求，请稍后再试。"
            )

    def _empty_result(
        self,
        conversation_id: Optional[str] = None,
        answer: str = "抱歉，我无法找到相关的信息来回答您的问题。"
    ) -> Dict[str, Any]:
        """返回空结果"""
        return {
            "answer": answer,
            "sources": [],
            "conversation_id": conversation_id
        }

    async def _resolve_dataset_by_tenant(self) -> Optional[str]:
        """当上游未提供dataset_id时，按租户回退选择一个可用数据集。"""
        if not self.tenant_id:
            return None

        query = """
            SELECT d.id
            FROM datasets d
            JOIN workspaces w ON d.workspace_id = w.id
            WHERE w.tenant_id = :tenant_id
            ORDER BY d.created_at ASC
            LIMIT 1
        """
        try:
            if self.db and hasattr(self.db, "fetch_one"):
                row = await self.db.fetch_one(query, {"tenant_id": str(self.tenant_id)})
                if row:
                    return str(row["id"] if hasattr(row, "__getitem__") else row[0])
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"[RAGAdapter] 使用databases实例回退选库失败: {e}")

        try:
            from infrastructure.database.session import AsyncSessionLocal
            from sqlalchemy import text

            async with AsyncSessionLocal() as session:
                result = await session.execute(text(query), {"tenant_id": str(self.tenant_id)})
                row = result.first()
                if row:
                    return str(row[0])
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"[RAGAdapter] 使用SQLAlchemy会话回退选库失败: {e}")

        return None