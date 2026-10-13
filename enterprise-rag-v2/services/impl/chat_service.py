"""
对话服务实现
"""

from typing import Optional, Dict, Any, List, AsyncIterator
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from infrastructure.database.models import Conversation, Message
from infrastructure.repositories.conversation_repository import (
    ConversationRepositoryImpl,
    MessageRepositoryImpl
)
from services.interfaces.chat_service import ChatService
from core.value_objects.pagination import Pagination, Page
from infrastructure.logging.logger import get_logger
from infrastructure.database.session import AsyncSessionLocal
from services.impl.user_llm_runtime import resolve_user_llm_runtime

logger = get_logger("services.impl.chat_service")


def _format_rag_failure_message(exc: BaseException) -> str:
    """
    RAG 链路任一步失败时给用户可读说明。原固定文案一律归咎 Qdrant，易误导（常为 LLM/嵌入/无文档）。
    """
    detail = (str(exc) or "").strip() or type(exc).__name__
    if len(detail) > 800:
        detail = detail[:800] + "…"
    return (
        f"处理失败：{detail}\n\n"
        "排查方向：\n"
        "· 向量检索：本服务会依次尝试 HTTP Qdrant → 本地嵌入式向量库 → 内存；若均失败请检查 QDRANT_URL 或启动 Docker Qdrant。\n"
        "· 大模型生成：请配置有效的 OPENAI_API_KEY（DeepSeek 兼容）或启动 Ollama（OLLAMA_URL）。\n"
        "· 知识库：确认已在该知识库中上传文档并完成索引。"
    )


class ChatServiceImpl(ChatService):
    """对话服务实现"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.conversation_repo = ConversationRepositoryImpl(session)
        self.message_repo = MessageRepositoryImpl(session)

    async def _get_dataset_workspace_id(self, dataset_id: UUID) -> Optional[str]:
        """查询数据集所属工作空间，用于创建会话时补齐 workspace_id。"""
        from infrastructure.database.models import Dataset
        from sqlalchemy import select

        result = await self.session.execute(
            select(Dataset.workspace_id).where(Dataset.id == str(dataset_id))
        )
        workspace_id = result.scalar_one_or_none()
        return str(workspace_id) if workspace_id else None

    async def verify_dataset_access(
        self,
        dataset_id: UUID,
        user_id: str,
        tenant_id: str,
        action: str = "read",
    ) -> None:
        """验证用户是否有权访问该数据集

        Args:
            dataset_id: 数据集ID
            user_id: 用户ID
            tenant_id: 租户ID
            action: "read" 或 "write"。公开数据集允许任何人 read，但拒绝非成员 write。
        """
        from infrastructure.database.models import Dataset, Workspace, WorkspaceMember
        from sqlalchemy import select

        # 1. 获取数据集和其所属的workspace
        result = await self.session.execute(
            select(Dataset, Workspace)
            .join(Workspace, Dataset.workspace_id == Workspace.id)
            .where(Dataset.id == str(dataset_id))
        )
        row = result.first()

        if not row:
            raise ValueError(f"数据集 {dataset_id} 不存在")

        dataset, workspace = row

        # 2. 公共数据集：读取允许所有人，写入需工作空间成员
        if getattr(dataset, 'is_public', False):
            if action == "read":
                return
            # write — 继续走成员检查

        # 3. 验证workspace属于用户的租户
        if workspace.tenant_id != tenant_id:
            raise PermissionError(f"您无权访问该数据集（跨租户访问被拒绝）")

        # 3.5 公共工作空间：同租户内所有用户自动可读，跳过成员检查
        workspace_meta = workspace.extra_metadata or {}
        if workspace_meta.get("is_public_workspace") is True:
            return

        # 4. 验证用户是该workspace的成员
        member_result = await self.session.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace.id,
                WorkspaceMember.user_id == user_id
            )
        )
        member = member_result.scalar_one_or_none()

        if not member:
            raise PermissionError(f"您不是该工作空间的成员，无权访问该数据集")

    async def chat(
        self,
        dataset_id: Optional[UUID],
        query: str,
        dataset_ids: Optional[List[UUID]] = None,
        conversation_id: Optional[UUID] = None,
        history: Optional[List[Dict[str, str]]] = None,
        retrieval_mode: str = "hybrid",
        top_k: int = 5,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> dict:
        """发送对话请求"""
        active_dataset_ids: List[UUID] = dataset_ids[:] if dataset_ids else []
        if dataset_id and dataset_id not in active_dataset_ids:
            active_dataset_ids.append(dataset_id)

        logger.info(
            f"开始处理对话请求, dataset_count={len(active_dataset_ids)}, query={query[:50]}"
        )

        if not active_dataset_ids:
            raise ValueError("至少需要一个可用数据集")

        # 防御：如果前端传入的 conversation_id 属于别的知识库，则创建新会话
        if conversation_id and user_id:
            existing = await self.conversation_repo.get_by_id(str(conversation_id))
            if existing and str(existing.user_id) != str(user_id):
                raise PermissionError("您无权写入该会话")
            if not existing or str(existing.dataset_id) != str(dataset_id):
                logger.warning(
                    "conversation_id=%s dataset_id=%s 不匹配（conv.dataset_id=%s），将创建新会话",
                    conversation_id, dataset_id,
                    str(existing.dataset_id) if existing else 'N/A'
                )
                conversation_id = None

        if not conversation_id and user_id:
            workspace_id = await self._get_dataset_workspace_id(active_dataset_ids[0])
            conv = await self.create_conversation(
                dataset_id=active_dataset_ids[0],
                user_id=user_id,
                title=query[:50] if len(query) > 50 else query,
                workspace_id=UUID(workspace_id) if workspace_id else None,
            )
            conversation_id = UUID(conv["id"])

        # 1. 向量检索相关文档
        from core.rag.embedding import EmbeddingService
        from core.rag.rag_engine import RAGEngineImpl
        from core.rag.collection_manager import CollectionManager
        from core.interfaces.rag_engine import QueryContext
        
        retrieved_documents = []
        answer = "抱歉，我无法找到相关的信息来回答您的问题。"
        
        try:
            # 获取数据集的工作空间ID
            from infrastructure.database.models import Dataset
            from sqlalchemy import select
            result = await self.session.execute(
                select(Dataset.workspace_id)
                .where(Dataset.id.in_([str(item) for item in active_dataset_ids]))
            )
            workspace_ids = result.scalars().all()
            workspace_id = workspace_ids[0] if workspace_ids else None
            
            logger.info(f"获取 workspace_id: {workspace_id}")
            
            if not workspace_id:
                raise ValueError(f"数据集 {dataset_id} 不存在")
            
            # 使用带 fallback 的向量存储工厂
            from core.rag.vector_store import create_vector_store
            from core.rag.embedding import get_embedding_service
            from core.rag.collection_manager import CollectionManager
            collection_name = CollectionManager.get_workspace_collection_name(workspace_id)
            vector_store = await create_vector_store(
                collection_name=collection_name,
                embedding_service=get_embedding_service(),
                use_memory_fallback=True
            )
            logger.info(f"使用 collection: {collection_name}")

            # 创建RAG引擎并确保使用后释放 HTTP 客户端资源
            runtime_credentials = await resolve_user_llm_runtime(self.session, user_id)
            rag_engine = RAGEngineImpl(
                vector_store=vector_store,
                db_session=self.session,
                runtime_provider=runtime_credentials.get("provider"),
                runtime_api_key=runtime_credentials.get("api_key"),
                runtime_base_url=runtime_credentials.get("base_url"),
                runtime_model=runtime_credentials.get("model"),
            )
            try:
                # 创建查询上下文
                # 当前向量集合按 workspace 划分；若跨工作空间，先限定到首个工作空间。
                workspace_dataset_ids = []
                if workspace_id:
                    workspace_dataset_result = await self.session.execute(
                        select(Dataset.id).where(Dataset.workspace_id == workspace_id)
                    )
                    workspace_dataset_id_set = {
                        str(item) for item in workspace_dataset_result.scalars().all()
                    }
                    workspace_dataset_ids = [
                        item for item in active_dataset_ids if str(item) in workspace_dataset_id_set
                    ]

                query_context = QueryContext(
                    workspace_id=UUID(workspace_id),
                    dataset_ids=workspace_dataset_ids or active_dataset_ids,
                    retrieval_mode=retrieval_mode,
                    top_k=top_k
                )

                logger.info(f"开始检索文档...")

                # 执行RAG查询
                rag_response = await rag_engine.query(
                    query=query,
                    context=query_context,
                    conversation_history=history,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            finally:
                await rag_engine.close()
            
            logger.info(f"检索完成，获得 {len(rag_response.retrieved_documents)} 个文档")
            
            answer = rag_response.answer
            retrieved_documents = [
                {
                    "content": doc.content,
                    "score": doc.score,
                    "metadata": doc.metadata,
                    "document_name": doc.document_name,
                    "document_id": doc.document_id,
                    "errata_warnings": doc.metadata.get("_errata", []),
                }
                for doc in rag_response.retrieved_documents
            ]
        except (ValueError, TypeError, RuntimeError, OSError, SQLAlchemyError, AttributeError) as e:
            logger.exception("RAG 非流式处理失败")
            answer = _format_rag_failure_message(e)
            retrieved_documents = []

        response = {
            "answer": answer,
            "conversation_id": str(conversation_id),
            "query": query,
            "retrieved_documents": retrieved_documents,
            "tokens_used": len(answer.split())
        }

        try:
            user_message = await self._save_message(
                conversation_id=conversation_id,
                role="user",
                content=query
            )

            assistant_message = await self._save_message(
                conversation_id=conversation_id,
                role="assistant",
                content=response["answer"],
                tokens_used=response["tokens_used"]
            )

            # 显式提交事务，确保消息被保存到数据库中
            await self.session.commit()

            response["message_id"] = str(assistant_message["id"])
        except (SQLAlchemyError, ValueError, TypeError, RuntimeError) as ex:
            logger.error("保存消息失败: %s", ex, exc_info=True)
            # 发生错误时回滚事务
            try:
                await self.session.rollback()
            except:
                pass

        return response

    async def chat_stream(
        self,
        dataset_id: UUID,
        query: str,
        conversation_id: Optional[UUID] = None,
        history: Optional[List[Dict[str, str]]] = None,
        retrieval_mode: str = "hybrid",
        top_k: int = 5,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> AsyncIterator[dict]:
        """流式对话请求"""
        logger.info(f"开始处理流式对话请求, dataset_id={dataset_id}, query={query[:50]}")

        # 防御：如果前端传入的 conversation_id 属于别的知识库，则创建新会话
        if conversation_id and user_id:
            existing = await self.conversation_repo.get_by_id(str(conversation_id))
            if existing and str(existing.user_id) != str(user_id):
                raise PermissionError("您无权写入该会话")
            if not existing or str(existing.dataset_id) != str(dataset_id):
                logger.warning(
                    "conversation_id=%s dataset_id=%s 不匹配（conv.dataset_id=%s），将创建新会话",
                    conversation_id, dataset_id,
                    str(existing.dataset_id) if existing else 'N/A'
                )
                conversation_id = None

        if not conversation_id and user_id:
            workspace_id = await self._get_dataset_workspace_id(dataset_id)
            conv = await self.create_conversation(
                dataset_id=dataset_id,
                user_id=user_id,
                title=query[:50] if len(query) > 50 else query,
                workspace_id=UUID(workspace_id) if workspace_id else None,
            )
            conversation_id = UUID(conv["id"])

        response_text = ""
        retrieved_chunks: List[Dict[str, Any]] = []
        turn_persisted = False

        async def _persist_stream_turn() -> None:
            """无论流是否正常结束、客户端是否断开，都尽量落库，避免切页后只能看到半截回复。"""
            nonlocal turn_persisted
            if turn_persisted or not conversation_id:
                return
            try:
                # 下游 RAG/LLM 可能在当前连接上留下 failed transaction（例如
                # provider 返回 401）。回滚是幂等的，先清理事务状态再写入
                # 用户问题和可读的错误答案。
                await self.session.rollback()
                await self._save_message(
                    conversation_id=conversation_id,
                    role="user",
                    content=query,
                )
                await self._save_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=response_text,
                    retrieved_chunks=retrieved_chunks,
                )
                # 显式提交事务，确保消息被保存到数据库中，即使客户端断开连接
                await self.session.commit()
                turn_persisted = True
                logger.info(
                    "已持久化流式回合: conversation_id=%s assistant_len=%s chunks=%s",
                    conversation_id,
                    len(response_text or ""),
                    len(retrieved_chunks or []),
                )
            except (SQLAlchemyError, ValueError, TypeError, RuntimeError) as ex:
                logger.error("流式回合落库失败: %s", ex, exc_info=True)
                # 发生错误时回滚事务
                try:
                    await self.session.rollback()
                except:
                    pass

        try:
            # 获取数据集的工作空间ID
            from infrastructure.database.models import Dataset
            from sqlalchemy import select
            result = await self.session.execute(
                select(Dataset.workspace_id).where(Dataset.id == str(dataset_id))
            )
            workspace_id = result.scalar_one_or_none()
            
            logger.info(f"获取 workspace_id: {workspace_id}")
            
            if not workspace_id:
                raise ValueError(f"数据集 {dataset_id} 不存在")
            
            # 使用带 fallback 的向量存储工厂
            from core.rag.vector_store import create_vector_store
            from core.rag.embedding import get_embedding_service
            from core.rag.collection_manager import CollectionManager
            from core.rag.rag_engine import RAGEngineImpl
            collection_name = CollectionManager.get_workspace_collection_name(workspace_id)
            vector_store = await create_vector_store(
                collection_name=collection_name,
                embedding_service=get_embedding_service(),
                use_memory_fallback=True
            )
            logger.info(f"使用 collection: {collection_name}")

            # 创建RAG引擎并确保使用后释放 HTTP 客户端资源
            runtime_credentials = await resolve_user_llm_runtime(self.session, user_id)
            rag_engine = RAGEngineImpl(
                vector_store=vector_store,
                db_session=self.session,
                runtime_provider=runtime_credentials.get("provider"),
                runtime_api_key=runtime_credentials.get("api_key"),
                runtime_base_url=runtime_credentials.get("base_url"),
                runtime_model=runtime_credentials.get("model"),
            )
            try:
                # 创建查询上下文
                from core.interfaces.rag_engine import QueryContext
                query_context = QueryContext(
                    workspace_id=UUID(workspace_id),
                    dataset_ids=[dataset_id],
                    retrieval_mode=retrieval_mode,
                    top_k=top_k
                )

                logger.info(f"开始检索文档...")

                # 执行RAG查询（流式）
                async for chunk in rag_engine.query_stream(
                    query=query,
                    context=query_context,
                    conversation_history=history,
                    temperature=temperature,
                    max_tokens=max_tokens
                ):
                    if chunk.get("type") == "token":
                        delta = chunk.get("delta", "")
                        response_text += delta
                        yield {
                            "delta": delta,
                            "conversation_id": str(conversation_id)
                        }
                    elif chunk.get("type") == "retrieval":
                        logger.info(f"检索完成，获得 {chunk.get('retrieved_count', 0)} 个文档，耗时 {chunk.get('retrieval_time_ms', 0)}ms")
                        retrieved_chunks = chunk.get("documents", []) or []
                        yield {
                            "event": "sources",
                            "data": [
                                {
                                    "content": doc.get("content", ""),
                                    "score": doc.get("score", 0),
                                    "metadata": doc.get("metadata", {}),
                                    "document_id": doc.get("document_id"),
                                    "document_name": doc.get("document_name"),
                                    "chunk_index": doc.get("chunk_index"),
                                    "errata_warnings": doc.get("metadata", {}).get("_errata", []),
                                }
                                for doc in retrieved_chunks
                            ],
                            "conversation_id": str(conversation_id)
                        }
            finally:
                await rag_engine.close()
        except (ValueError, TypeError, RuntimeError, OSError, SQLAlchemyError, AttributeError) as e:
            logger.exception("RAG 流式处理失败")
            error_message = _format_rag_failure_message(e)
            # 某些下游调用（例如 LLM 返回 401）可能让当前数据库事务进入
            # failed 状态。先回滚，再由 finally 持久化可读的失败消息，避免
            # Celery 任务成功但前端永远停留在“处理中”。
            try:
                await self.session.rollback()
            except Exception:
                logger.warning("RAG 失败后的事务回滚失败", exc_info=True)
            yield {
                "delta": error_message,
                "conversation_id": str(conversation_id),
            }
            response_text = error_message
        finally:
            await _persist_stream_turn()

        # 明确通知前端流式结束，并返回会话信息用于刷新会话状态
        yield {
            "event": "done",
            "data": {
                "conversation": {
                    "id": str(conversation_id),
                    "dataset_id": str(dataset_id)
                }
            },
            "conversation_id": str(conversation_id)
        }

    async def create_conversation(
        self,
        dataset_id: UUID,
        user_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        visibility: str = "private",
        workspace_id: Optional[UUID] = None
    ) -> dict:
        """创建会话（支持可见性设置）"""
        conversation = Conversation(
            dataset_id=str(dataset_id),
            user_id=user_id,
            title=title or f"New conversation",
            visibility=visibility or "private",
            workspace_id=str(workspace_id) if workspace_id else None,
            extra_metadata=metadata or {}
        )

        try:
            created = await self.conversation_repo.create(conversation)
            # 显式提交事务，确保会话被保存到数据库中
            await self.session.commit()

            return {
                "id": str(created.id),
                "dataset_id": str(created.dataset_id),
                "user_id": created.user_id,
                "title": created.title,
                "visibility": created.visibility,
                "workspace_id": str(created.workspace_id) if created.workspace_id else None,
                "metadata": created.extra_metadata,
                "created_at": created.created_at.isoformat() if created.created_at else None,
                "updated_at": created.updated_at.isoformat() if created.updated_at else None
            }
        except (SQLAlchemyError, ValueError, TypeError, RuntimeError) as ex:
            logger.error("创建会话失败: %s", ex, exc_info=True)
            # 发生错误时回滚事务
            try:
                await self.session.rollback()
            except:
                pass
            raise

    async def get_conversation(self, conversation_id: UUID) -> Optional[dict]:
        """获取会话详情（包含可见性信息）"""
        conversation = await self.conversation_repo.get_by_id(str(conversation_id))
        if not conversation:
            return None

        return {
            "id": str(conversation.id),
            "dataset_id": str(conversation.dataset_id),
            "user_id": conversation.user_id,
            "title": conversation.title,
            "visibility": conversation.visibility or "private",
            "workspace_id": str(conversation.workspace_id) if conversation.workspace_id else None,
            "metadata": conversation.extra_metadata or {},
            "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
            "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None
        }

    async def update_conversation(
        self,
        conversation_id: UUID,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> dict:
        """更新会话"""
        conversation = await self.conversation_repo.get_by_id(str(conversation_id))
        if not conversation:
            raise ValueError("会话不存在")

        if title is not None:
            conversation.title = title
        if metadata is not None:
            conversation.extra_metadata = metadata

        updated = await self.conversation_repo.update(conversation)

        return {
            "id": str(updated.id),
            "dataset_id": str(updated.dataset_id),
            "title": updated.title,
            "metadata": updated.extra_metadata,
            "created_at": updated.created_at.isoformat() if updated.created_at else None,
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None
        }

    async def delete_conversation(self, conversation_id: UUID) -> bool:
        """删除会话"""
        conversation = await self.conversation_repo.get_by_id(str(conversation_id))
        if not conversation:
            return False

        await self.conversation_repo.delete(str(conversation_id))
        return True

    async def list_conversations(
        self,
        user_id: Optional[str] = None,
        dataset_id: Optional[UUID] = None,
        keyword: Optional[str] = None,
        pagination: Optional[Pagination] = None
    ) -> Page:
        """查询会话列表"""
        from sqlalchemy import select, func
        from infrastructure.database.models import Conversation
        
        # 构建查询，只返回用户自己的会话
        query = select(Conversation)
        if user_id:
            query = query.where(Conversation.user_id == user_id)
        if dataset_id:
            query = query.where(Conversation.dataset_id == str(dataset_id))
        if keyword:
            from sqlalchemy import or_
            keyword_filter = f"%{keyword}%"
            query = query.where(Conversation.title.ilike(keyword_filter))
        
        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # 应用分页和排序
        if pagination is None:
            pagination = Pagination(page=1, page_size=20)
        
        query = query.order_by(Conversation.updated_at.desc())
        query = query.offset((pagination.page - 1) * pagination.page_size).limit(pagination.page_size)
        
        result = await self.session.execute(query)
        conversations = result.scalars().all()
        
        items = []
        for conv in conversations:
            items.append({
                "id": str(conv.id),
                "dataset_id": str(conv.dataset_id),
                "title": conv.title,
                "metadata": conv.extra_metadata or {},
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None
            })

        return Page(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )

    async def get_conversation_messages(self, conversation_id: UUID) -> List[dict]:
        """获取会话消息历史"""
        messages = await self.message_repo.get_by_conversation(str(conversation_id))

        result = []
        for msg in messages:
            result.append({
                "id": str(msg.id),
                "conversation_id": str(msg.conversation_id),
                "role": msg.role,
                "content": msg.content,
                "retrieved_chunks": msg.retrieved_chunks,
                "tokens_used": msg.tokens_used,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            })

        return result

    async def _save_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
        tokens_used: Optional[int] = None
    ) -> dict:
        """保存消息"""
        message = Message(
            conversation_id=str(conversation_id),
            role=role,
            content=content,
            retrieved_chunks=retrieved_chunks or [],
            tokens_used=tokens_used
        )

        created = await self.message_repo.create(message)

        conversation = await self.conversation_repo.get_by_id(str(conversation_id))
        if conversation:
            from datetime import datetime, timezone
            conversation.updated_at = datetime.now(timezone.utc)
            await self.conversation_repo.update(conversation)

        return {
            "id": str(created.id),
            "conversation_id": str(created.conversation_id),
            "role": created.role,
            "content": created.content,
            "tokens_used": created.tokens_used,
            "created_at": created.created_at.isoformat() if created.created_at else None
        }

    async def list_conversations_with_permissions(
        self,
        user_id: str,
        filters: Optional[Dict[str, Any]] = None,
        pagination=None
    ):
        """基于权限过滤的会话列表查询"""
        
        from sqlalchemy import select, func, or_, and_
        from infrastructure.database.models import Conversation
        from core.value_objects.pagination import Pagination, Page
        
        if pagination is None:
            pagination = Pagination(page=1, page_size=20)
        
        filters = filters or {}
        
        # 构建基础查询 - 用户可以访问的会话：
        # 1. 自己创建的会话（任何可见性）
        # 2. WORKSPACE/TENANT级别的会话（根据角色）
        query = select(Conversation).where(
            or_(
                # 用户创建的所有会话
                Conversation.user_id == user_id,
                # 或者是共享会话（需要后续通过PermissionChecker验证）
                and_(
                    Conversation.visibility.in_(["workspace", "tenant"]),
                    Conversation.user_id != user_id
                )
            )
        )
        
        # 应用额外过滤器
        if filters.get("dataset_id"):
            query = query.where(Conversation.dataset_id == filters["dataset_id"])
        
        if filters.get("workspace_id"):
            query = query.where(Conversation.workspace_id == filters["workspace_id"])
        
        if filters.get("visibility"):
            query = query.where(Conversation.visibility == filters["visibility"])
        
        if filters.get("keyword"):
            keyword_filter = f"%{filters['keyword']}%"
            query = query.where(Conversation.title.ilike(keyword_filter))
        
        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0
        
        # 应用分页和排序
        query = query.order_by(Conversation.updated_at.desc())
        query = query.offset((pagination.page - 1) * pagination.page_size).limit(pagination.page_size)
        
        result = await self.session.execute(query)
        conversations = result.scalars().all()
        
        items = []
        for conv in conversations:
            items.append({
                "id": str(conv.id),
                "dataset_id": str(conv.dataset_id),
                "user_id": str(conv.user_id),
                "title": conv.title or "",
                "visibility": conv.visibility or "private",
                "workspace_id": str(conv.workspace_id) if conv.workspace_id else None,
                "message_count": 0,
                "metadata": conv.extra_metadata or {},
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None
            })
        
        return Page(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size
        )

    async def update_conversation_visibility(
        self,
        conversation_id: UUID,
        user_id: str,
        new_visibility: str
    ) -> dict:
        """更新会话可见性级别"""
        
        from services.permission_checker import PermissionChecker, PermissionAction
        
        permission_checker = PermissionChecker()
        
        async with AsyncSessionLocal() as session:
            has_permission = await permission_checker.check_conversation_access(
                user_id=user_id,
                conversation_id=conversation_id,
                action=PermissionAction.UPDATE,
                session=session
            )
            
            if not has_permission:
                raise PermissionError("You do not have permission to modify this conversation")
        
        conversation = await self.conversation_repo.get_by_id(str(conversation_id))
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        old_visibility = conversation.visibility
        
        conversation.visibility = new_visibility
        updated = await self.conversation_repo.update(conversation)
        
        return {
            "id": str(updated.id),
            "dataset_id": str(updated.dataset_id),
            "title": updated.title,
            "visibility": updated.visibility,
            "old_visibility": old_visibility,
            "message": f"Visibility changed from {old_visibility} to {new_visibility}",
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None
        }
