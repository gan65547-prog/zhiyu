"""
查询处理服务 - OpenClaw混合架构核心

职责:
  处理来自OpenClaw的查询请求，协调以下组件:
  1. UserMappingService → 用户身份映射
  2. QuotaService → 配额检查 + 使用量计数
  3. RAG Service → 知识库检索
  4. Response Formatter → 格式化响应（含升级提示）

集成消息路由关键路径:
  用户查询 → 配额检查 → [超限?] → 返回升级提示 / 正常查询
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

from apps.integration.models.request import ChatRequest
from apps.integration.models.response import (
    ChatResponse,
    SourceInfo,
    QuotaInfo,
    SuggestedAction,
)
from core.decorators import log_exceptions
from infrastructure.logging.logger import get_logger

logger = get_logger(__name__)


class QueryService:
    """查询处理服务"""
    
    def __init__(
        self,
        db=None,
        redis=None,
        quota_service=None,
        rag_service=None,
        user_mapping_service=None
    ):
        self.db = db
        self.redis = redis
        self.quota_service = quota_service
        self.rag_service = rag_service
        self.user_mapping_service = user_mapping_service or (
            __import__('apps.integration.services.user_mapping', fromlist=['UserMappingService']).UserMappingService(
                db=db, redis=redis, quota_service=quota_service
            )
        )
    
    async def handle_query(
        self,
        platform: str,
        platform_user_id: str,
        request_body: ChatRequest,
        tenant_id: Optional[int] = None,
        system_user_id: Optional[int] = None,
        app_config_id: Optional[str] = None,
        kb_pref_dataset_id: Optional[str] = None,
    ) -> ChatResponse:
        """
        处理查询请求的核心方法
        
        Args:
            platform: 平台标识
            platform_user_id: 平台用户ID
            request_body: 查询请求体
            tenant_id: 租户ID (可选，如果已从映射中获取)
            system_user_id: 系统用户ID (可选)
            app_config_id: 平台应用配置ID (v2.1 多租户架构)
        
        Returns:
            ChatResponse (包含回答、来源、配额信息等)
        """
        
        logger.info(
            f"[QueryService] 开始处理查询",
            extra={
                "platform": platform,
                "query": request_body.query[:50],
                "has_conversation_id": request_body.conversation_id is not None,
                "app_config_id": app_config_id
            }
        )
        
        # ===== Step 1: 用户身份映射 =====
        # 优先使用路由层传入的tenant_id，避免被历史映射错误覆盖到其他租户
        routed_tenant_id = tenant_id
        if not system_user_id or not tenant_id:
            from apps.integration.config import settings
            
            mapping_result = await self.user_mapping_service.get_or_create_user(
                platform=platform,
                platform_user_id=platform_user_id,
                auto_register=settings.auto_register_enabled,
                app_config_id=app_config_id
            )
            
            if "bind_code" in mapping_result and mapping_result["bind_code"]:
                return self._create_bind_required_response(mapping_result["bind_code"])
            
            system_user_id = mapping_result["system_user_id"]
            mapped_tenant_id = mapping_result["tenant_id"]
            if routed_tenant_id:
                if str(mapped_tenant_id) != str(routed_tenant_id):
                    logger.warning(
                        f"[QueryService] 检测到租户不一致，保持路由租户: "
                        f"routed={routed_tenant_id}, mapped={mapped_tenant_id}"
                    )
                tenant_id = routed_tenant_id
            else:
                tenant_id = mapped_tenant_id
        
        # ===== Step 2: 检查管理员配置的资源上限 =====
        quota_check_result = await self._check_quota(tenant_id)
        
        if quota_check_result.get("exceeded"):
            logger.info(
                f"[QueryService] 配额超限，返回升级提示",
                extra={"tenant_id": tenant_id}
            )
            return self._create_quota_exceeded_response(quota_check_result)
        
        # ===== Step 3: RAG知识库检索 =====
        # 支持 #知识库名称 前缀选择知识库
        kb_name, actual_query = self._extract_kb_selector(request_body.query)
        if kb_name:
            logger.info(f"[QueryService] 用户指定知识库: {kb_name}, 原始查询: {request_body.query[:50]}")

        try:
            rag_result = await self._perform_rag_search(
                query=actual_query if kb_name else request_body.query,
                tenant_id=tenant_id,
                user_id=system_user_id,
                conversation_id=request_body.conversation_id,
                kb_name=kb_name,
                kb_pref_dataset_id=kb_pref_dataset_id,
            )
            
        except Exception as e:
            logger.error(f"[QueryService] RAG检索失败: {e}", exc_info=True)
            rag_result = {
                "answer": "系统繁忙，请稍后再试。如果问题持续存在，请联系技术支持。",
                "sources": [],
                "conversation_id": request_body.conversation_id
            }
        
        # ===== Step 4: 增加使用量 =====
        try:
            new_usage = await self._increment_quota(tenant_id)
            logger.debug(f"[QueryService] 使用量增加: tenant={tenant_id}, new_value={new_usage}")
            
        except Exception as e:
            logger.warning(f"[QueryService] 增加使用量失败(不影响结果): {e}")
        
        # ===== Step 5: 构建并返回响应 =====
        response = self._build_success_response(rag_result, quota_check_result)
        
        logger.info(
            f"[QueryService] 查询完成",
            extra={
                "has_answer": bool(response.answer),
                "source_count": len(response.sources),
                "quota_exceeded": response.quota_exceeded
            }
        )
        
        return response
    
    async def _check_quota(self, tenant_id: int) -> Dict[str, Any]:
        """检查配额"""
        if not self.quota_service:
            return {"exceeded": False, "current": 0, "limit": 999999}
        
        try:
            from apps.integration.config import settings
            
            is_ok, current, limit_val, percentage = await self.quota_service.check_quota(
                str(tenant_id),
                settings.quota_dimension_api_calls
            )
            
            return {
                "exceeded": not is_ok,
                "current": current,
                "limit": limit_val,
                "percentage": percentage
            }
            
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"配额检查失败: {e}, 允许继续")
            return {"exceeded": False, "current": 0, "limit": 999999}
    
    @log_exceptions(__name__)
    async def _perform_rag_search(
        self,
        query: str,
        tenant_id: int,
        user_id: int,
        conversation_id: Optional[str],
        kb_name: Optional[str] = None,
        kb_pref_dataset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """执行RAG知识库检索

        知识库选择优先级:
          1. #知识库名称 前缀（最高）
          2. 会话级 KB 偏好（卡片菜单选择）
          3. 默认策略（用户当前工作空间）
        """
        if not self.rag_service:
            logger.info(f"[QueryService] rag_service未配置，尝试创建RAGServiceAdapter")
            try:
                from apps.integration.services.rag_service_adapter import RAGServiceAdapter
                self.rag_service = RAGServiceAdapter(db=self.db, tenant_id=str(tenant_id))
                logger.info(f"[QueryService] RAGServiceAdapter创建成功")
            except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.warning(f"[QueryService] 创建RAGServiceAdapter失败: {e}")

        if not self.rag_service:
            logger.warning("[QueryService] 无法创建RAG服务，返回模拟数据")
            return {
                "answer": f"[Mock RAG回复] 您的问题是: '{query}'\n\n"
                       f"Phase 2将对接真实的RAG检索服务。",
                "sources": [
                    SourceInfo(
                        document_title="示例文档.md",
                        dataset_name="技术文档",
                        relevance_score=0.95,
                        content_snippet="这是示例内容..."
                    )
                ],
                "conversation_id": conversation_id
            }

        # 知识库选择优先级: #指定 > 会话偏好 > 默认
        if kb_name:
            dataset_ids = await self._resolve_dataset_by_name(kb_name, tenant_id, user_id)
            if dataset_ids:
                logger.info(
                    f"[QueryService] 使用 #指定 知识库: {kb_name}, dataset_ids={dataset_ids}"
                )
            else:
                logger.warning(
                    f"[QueryService] 未找到知识库 '{kb_name}'，回退到默认策略"
                )
                dataset_ids = await self._get_default_dataset_ids(tenant_id, user_id)
        elif kb_pref_dataset_id:
            import uuid as _uuid
            dataset_ids = [_uuid.UUID(kb_pref_dataset_id)]
            logger.info(
                f"[QueryService] 使用会话偏好知识库: dataset_id={kb_pref_dataset_id}"
            )
        else:
            dataset_ids = await self._get_default_dataset_ids(tenant_id, user_id)

        result = await self.rag_service.search(
            query=query,
            dataset_id=dataset_ids[0] if dataset_ids else None,
            dataset_ids=dataset_ids,
            user_id=user_id,
            conversation_id=conversation_id
        )

        return result
    
    @log_exceptions(__name__)
    async def _increment_quota(self, tenant_id: int) -> int:
        """增加配额使用量"""
        if not self.quota_service:
            return 0

        from apps.integration.config import settings
        
        new_value = await self.quota_service.increment_usage(
            str(tenant_id),
            settings.quota_dimension_api_calls,
            1
        )
        
        return new_value
    
    async def _get_default_dataset_ids(self, tenant_id: int, user_id: int) -> List[UUID]:
        """获取用户可访问的数据集ID列表（优先当前工作空间，避免仅检索单数据集）"""
        if not self.db:
            logger.warning("[QueryService] 数据库未初始化，无法获取数据集")
            return []

        try:
            from uuid import UUID
            tenant_id_str = str(tenant_id)
            user_id_str = str(user_id)
            logger.info(
                f"[QueryService] 获取可访问数据集: tenant={tenant_id_str}, user={user_id_str}"
            )

            query = """
                SELECT d.id, w.id AS workspace_id
                FROM datasets d
                JOIN workspaces w ON d.workspace_id = w.id
                JOIN users u ON u.id = :user_id
                LEFT JOIN workspace_members wm
                       ON wm.workspace_id = w.id AND wm.user_id = :user_id
                WHERE w.tenant_id = :tenant_id
                  AND (u.is_superuser = TRUE OR wm.id IS NOT NULL)
                ORDER BY
                  CASE WHEN u.current_workspace_id = w.id THEN 0 ELSE 1 END,
                  d.created_at ASC
            """

            rows = []
            try:
                if hasattr(self.db, "fetch_all"):
                    rows = await self.db.fetch_all(
                        query, {"tenant_id": tenant_id_str, "user_id": user_id_str}
                    )
                elif hasattr(self.db, "execute"):
                    result = await self.db.execute(
                        query, {"tenant_id": tenant_id_str, "user_id": user_id_str}
                    )
                    if hasattr(result, "fetchall"):
                        rows = await result.fetchall()
            except (RuntimeError, ValueError, TypeError, AttributeError) as primary_query_error:
                logger.warning(
                    f"[QueryService] 用户权限选库查询失败，改走租户级回退: "
                    f"tenant={tenant_id_str}, user={user_id_str}, err={primary_query_error}"
                )

            if not rows:
                logger.warning(
                    f"[QueryService] 未找到可访问数据集，尝试租户级回退: tenant={tenant_id_str}, user={user_id_str}"
                )
                fallback_query = """
                    SELECT d.id, w.id AS workspace_id
                    FROM datasets d
                    JOIN workspaces w ON d.workspace_id = w.id
                    WHERE w.tenant_id = :tenant_id
                    ORDER BY d.created_at ASC
                """
                if hasattr(self.db, "fetch_all"):
                    rows = await self.db.fetch_all(fallback_query, {"tenant_id": tenant_id_str})
                elif hasattr(self.db, "execute"):
                    result = await self.db.execute(fallback_query, {"tenant_id": tenant_id_str})
                    if hasattr(result, "fetchall"):
                        rows = await result.fetchall()
                if not rows:
                    logger.warning(f"[QueryService] 租户级回退仍未找到数据集: tenant={tenant_id_str}")
                    return []

            first_row = rows[0]
            preferred_workspace_id = (
                first_row["workspace_id"] if hasattr(first_row, "__getitem__") else first_row[1]
            )

            dataset_ids: List[UUID] = []
            for row in rows:
                row_workspace_id = row["workspace_id"] if hasattr(row, "__getitem__") else row[1]
                if str(row_workspace_id) != str(preferred_workspace_id):
                    continue
                dataset_id = row["id"] if hasattr(row, "__getitem__") else row[0]
                dataset_ids.append(UUID(str(dataset_id)))

            logger.info(
                f"[QueryService] 选择数据集数量: {len(dataset_ids)}, workspace={preferred_workspace_id}"
            )
            return dataset_ids

        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"[QueryService] 获取默认数据集失败: {e}", exc_info=True)
            return []
    
    @staticmethod
    def _extract_kb_selector(query: str) -> tuple:
        """从查询文本中提取知识库选择器

        支持格式:
          #知识库名称 你的问题
          #知识库名称# 你的问题

        Returns:
            (kb_name, actual_query) — kb_name 为 None 表示未指定
        """
        import re
        text = query.strip()
        m = re.match(r"^#([^\s#]+)\s*#?\s*", text)
        if m:
            kb_name = m.group(1)
            actual_query = text[m.end():].strip()
            return kb_name, actual_query
        return None, query

    async def _resolve_dataset_by_name(
        self, kb_name: str, tenant_id: int, user_id: int
    ) -> List[UUID]:
        """根据知识库名称（模糊匹配）解析 dataset_ids"""
        if not self.db:
            return []

        try:
            query = """
                SELECT d.id
                FROM datasets d
                JOIN workspaces w ON d.workspace_id = w.id
                JOIN users u ON u.id = :user_id
                LEFT JOIN workspace_members wm
                       ON wm.workspace_id = w.id AND wm.user_id = :user_id
                WHERE w.tenant_id = :tenant_id
                  AND (u.is_superuser = TRUE OR wm.id IS NOT NULL)
                  AND d.name ILIKE :kb_name
                ORDER BY
                  CASE WHEN u.current_workspace_id = w.id THEN 0 ELSE 1 END,
                  d.created_at ASC
            """

            rows = []
            if hasattr(self.db, "fetch_all"):
                rows = await self.db.fetch_all(
                    query, {"tenant_id": str(tenant_id), "user_id": str(user_id), "kb_name": f"%{kb_name}%"}
                )
            elif hasattr(self.db, "execute"):
                result = await self.db.execute(
                    query, {"tenant_id": str(tenant_id), "user_id": str(user_id), "kb_name": f"%{kb_name}%"}
                )
                if hasattr(result, "fetchall"):
                    rows = await result.fetchall()

            ids: List[UUID] = []
            for row in rows:
                dataset_id = row["id"] if hasattr(row, "__getitem__") else row[0]
                ids.append(UUID(str(dataset_id)))

            if not ids:
                logger.warning(f"[QueryService] 未找到匹配的知识库: {kb_name}")
            return ids

        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"[QueryService] 按名称解析知识库失败: {e}", exc_info=True)
            return []

    async def get_available_kb_list(self, tenant_id: int, user_id: int) -> List[Dict[str, str]]:
        """获取用户可访问的知识库列表（用于选择菜单）"""
        if not self.db:
            return []

        try:
            query = """
                SELECT d.id, d.name, d.description
                FROM datasets d
                JOIN workspaces w ON d.workspace_id = w.id
                JOIN users u ON u.id = :user_id
                LEFT JOIN workspace_members wm
                       ON wm.workspace_id = w.id AND wm.user_id = :user_id
                WHERE w.tenant_id = :tenant_id
                  AND (u.is_superuser = TRUE OR wm.id IS NOT NULL)
                ORDER BY
                  CASE WHEN u.current_workspace_id = w.id THEN 0 ELSE 1 END,
                  d.name ASC
            """
            rows = []
            if hasattr(self.db, "fetch_all"):
                rows = await self.db.fetch_all(
                    query, {"tenant_id": str(tenant_id), "user_id": str(user_id)}
                )
            elif hasattr(self.db, "execute"):
                result = await self.db.execute(
                    query, {"tenant_id": str(tenant_id), "user_id": str(user_id)}
                )
                if hasattr(result, "fetchall"):
                    rows = await result.fetchall()

            result = []
            for row in rows:
                kb_id = row["id"] if hasattr(row, "__getitem__") else row[0]
                name = row["name"] if hasattr(row, "__getitem__") else row[1]
                desc = row["description"] if hasattr(row, "__getitem__") else row[2] if len(row) > 2 else ""
                result.append({"id": str(kb_id), "name": name, "description": desc or ""})

            return result

        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.error(f"[QueryService] 获取知识库列表失败: {e}", exc_info=True)
            return []

    def _create_bind_required_response(self, bind_code: str) -> ChatResponse:
        """创建需要绑定的响应"""
        return ChatResponse(
            success=True,
            answer=(
                f"欢迎使用企业RAG知识库！\n\n"
                f"为了提供更好的服务，请先完成账号绑定。\n\n"
                f"绑定码: **{bind_code}**\n\n"
                f"请访问绑定页面完成操作。"
            ),
            sources=[],
            quota_exceeded=False
        )
    
    def _create_quota_exceeded_response(self, quota_info: Dict) -> ChatResponse:
        """创建资源上限响应。"""
        current = quota_info["current"]
        limit_val = quota_info["limit"]
        percentage = round(current / limit_val * 100, 1) if limit_val > 0 else 100
        message = f"当前资源使用量已达到部署管理员设置的上限（{current}/{limit_val}），请联系管理员调整。"
        
        return ChatResponse(
            success=True,
            answer=message,
            sources=[],
            quota_exceeded=True,
            suggested_actions=[
                SuggestedAction(
                    type="view_usage",
                    title="📊 查看使用情况",
                    url="/api/v1/quotas/usage"
                )
            ]
        )
    
    def _build_success_response(
        self,
        rag_result: Dict,
        quota_check: Dict
    ) -> ChatResponse:
        """构建成功响应"""
        
        answer = rag_result.get("answer", "")
        sources_raw = rag_result.get("sources", [])
        
        # 格式化来源信息
        sources = []
        for src in sources_raw[:3]:  # 最多返回3个来源
            if isinstance(src, dict):
                sources.append(SourceInfo(
                    document_title=src.get("document_title", "未知文档"),
                    dataset_name=src.get("dataset_name", "未知知识库"),
                    relevance_score=float(src.get("relevance_score", 0)),
                    content_snippet=src.get("content_snippet")
                ))
            elif isinstance(src, SourceInfo):
                sources.append(src)
        
        # 构建配额信息
        current = quota_check.get("current", 0) + 1  # 已+1
        limit_val = quota_check.get("limit", 999999)
        remaining = max(0, limit_val - current)
        percentage = round(current / limit_val * 100, 1) if limit_val > 0 else 0
        
        quota_info = QuotaInfo(
            dimension="chat_messages_monthly",
            current=current,
            limit=limit_val,
            remaining=remaining,
            percentage=percentage
        )
        
        # 如果接近上限 (>80%)，在回答末尾添加提醒
        if percentage > 80 and percentage < 100:
            answer += f"\n\n⚠️ 本月AI对话额度已使用 {percentage}% ({current}/{limit_val})"
        
        return ChatResponse(
            success=True,
            answer=answer,
            sources=sources,
            conversation_id=rag_result.get("conversation_id"),
            quota_info=quota_info,
            quota_exceeded=False,
            suggested_actions=[]
        )
