"""
租户服务实现
包含完整的配额管理功能
"""

from typing import Optional, Dict, Any
import json
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.exc import SQLAlchemyError

from infrastructure.database.models import Tenant, User, Workspace, Dataset, Document, DocumentCopyStatus
from infrastructure.repositories.tenant_repository import TenantRepositoryImpl
from services.interfaces.tenant_service import TenantService
from services.interfaces.user_service import UserService
from services.impl.user_service_impl import UserServiceImpl
from services.interfaces.workspace_service import WorkspaceService
from services.impl.workspace_service import WorkspaceServiceImpl
from services.interfaces.dataset_service import DatasetService
from services.impl.dataset_service import DatasetServiceImpl
from services.interfaces.document_copy_service import DocumentCopyService
from services.impl.document_copy_service import DocumentCopyService as DocumentCopyServiceImpl
from services.audit.service import AuditService, AuditAction
from core.value_objects.pagination import Pagination, Page
from core.config import get_settings
from core.exceptions import QuotaExceededError
from infrastructure.logging.logger import get_logger


settings = get_settings()
logger = get_logger("services.impl.tenant_service")


DEFAULT_QUOTAS = {
    "max_users": -1,
    "max_workspaces": -1,
    "max_datasets": -1,
    "max_documents": -1,
    "max_storage_mb": -1,
    "max_api_calls_per_day": -1,
}


def _to_iso_datetime(value) -> Optional[str]:
    """兼容 datetime 与字符串时间，统一返回 ISO 字符串。"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _normalize_enum_value(value, default: str) -> str:
    """将枚举/字符串值统一为小写 value，兼容历史大写标签。"""
    if value is None:
        return default
    if hasattr(value, "value"):
        return str(value.value).lower()
    raw = str(value).strip()
    if not raw:
        return default
    return raw.lower()


def _normalize_metadata(value) -> Dict[str, Any]:
    """兼容 JSON/字符串/None，统一输出 dict。"""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return {}
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
    return {}


class TenantServiceImpl(TenantService):
    """租户服务实现"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.tenant_repo = TenantRepositoryImpl(session)
        self.audit_service = AuditService(session)

    def _get_quota_limits(self, plan: str) -> Dict[str, int]:
        """开源自托管版默认不按历史计划字段限制租户资源。"""
        return dict(DEFAULT_QUOTAS)

    async def _get_current_usage(self, tenant_id: UUID) -> Dict[str, int]:
        """获取租户当前资源使用量"""
        # users/workspaces 表中的 tenant_id 为字符串列，统一按字符串比较避免 uuid/varchar 运算符冲突
        tenant_key = str(tenant_id)
        user_count = await self.session.execute(
            select(func.count()).select_from(User).where(User.tenant_id == tenant_key)
        )
        workspace_count = await self.session.execute(
            select(func.count()).select_from(Workspace).where(Workspace.tenant_id == tenant_key)
        )
        
        dataset_query = select(func.count()).select_from(Dataset).join(Workspace).where(
            Workspace.tenant_id == tenant_key
        )
        dataset_count = await self.session.execute(dataset_query)
        
        doc_query = select(func.count()).select_from(Document).join(Dataset).join(Workspace).where(
            Workspace.tenant_id == tenant_key
        )
        document_count = await self.session.execute(doc_query)
        
        storage_query = select(func.sum(Document.file_size)).select_from(Document).join(
            Dataset
        ).join(Workspace).where(Workspace.tenant_id == tenant_key)
        storage_result = await self.session.execute(storage_query)
        storage_bytes = storage_result.scalar() or 0
        storage_mb = storage_bytes / (1024 * 1024)

        return {
            "user_count": user_count.scalar() or 0,
            "workspace_count": workspace_count.scalar() or 0,
            "dataset_count": dataset_count.scalar() or 0,
            "document_count": document_count.scalar() or 0,
            "storage_mb": round(storage_mb, 2),
        }

    async def check_quota(self, tenant_id: UUID, resource_type: str) -> bool:
        """检查配额是否充足"""
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            return False

        plan = tenant.plan.value if hasattr(tenant.plan, 'value') else tenant.plan
        quotas = self._get_quota_limits(plan)
        usage = await self._get_current_usage(tenant_id)

        quota_mapping = {
            "user": ("user_count", "max_users"),
            "workspace": ("workspace_count", "max_workspaces"),
            "dataset": ("dataset_count", "max_datasets"),
            "document": ("document_count", "max_documents"),
            "storage": ("storage_mb", "max_storage_mb"),
        }

        if resource_type not in quota_mapping:
            return True

        usage_key, limit_key = quota_mapping[resource_type]
        current = usage[usage_key]
        limit = quotas[limit_key]

        if limit == -1:
            return True

        return current < limit

    async def check_quota_and_raise(self, tenant_id: UUID, resource_type: str) -> None:
        """检查配额，不足时抛出异常"""
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise ValueError("租户不存在")

        plan = tenant.plan.value if hasattr(tenant.plan, 'value') else tenant.plan
        quotas = self._get_quota_limits(plan)
        usage = await self._get_current_usage(tenant_id)

        quota_mapping = {
            "user": ("user_count", "max_users"),
            "workspace": ("workspace_count", "max_workspaces"),
            "dataset": ("dataset_count", "max_datasets"),
            "document": ("document_count", "max_documents"),
            "storage": ("storage_mb", "max_storage_mb"),
        }

        if resource_type not in quota_mapping:
            return

        usage_key, limit_key = quota_mapping[resource_type]
        current = usage[usage_key]
        limit = quotas[limit_key]

        if limit == -1:
            return

        if current >= limit:
            raise QuotaExceededError(resource_type, current, limit)

    async def get_quota_status(self, tenant_id: UUID) -> Dict[str, Any]:
        """获取租户配额状态"""
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise ValueError("租户不存在")

        plan = tenant.plan.value if hasattr(tenant.plan, 'value') else tenant.plan
        quotas = self._get_quota_limits(plan)
        usage = await self._get_current_usage(tenant_id)

        status = {}
        warnings = []

        for resource_type, (usage_key, limit_key) in {
            "user": ("user_count", "max_users"),
            "workspace": ("workspace_count", "max_workspaces"),
            "dataset": ("dataset_count", "max_datasets"),
            "document": ("document_count", "max_documents"),
            "storage": ("storage_mb", "max_storage_mb"),
        }.items():
            current = usage[usage_key]
            limit = quotas[limit_key]
            
            if limit == -1:
                percentage = 0
                is_unlimited = True
            else:
                percentage = round((current / limit) * 100, 2) if limit > 0 else 0
                is_unlimited = False
                
                if percentage >= 90:
                    warnings.append({
                        "resource_type": resource_type,
                        "current": current,
                        "limit": limit,
                        "percentage": percentage,
                        "severity": "critical" if percentage >= 100 else "warning"
                    })

            status[resource_type] = {
                "current": current,
                "limit": limit,
                "percentage": percentage,
                "is_unlimited": is_unlimited,
                "available": limit == -1 or limit - current
            }

        return {
            "tenant_id": str(tenant_id),
            "plan": plan,
            "quotas": quotas,
            "usage": usage,
            "status": status,
            "warnings": warnings
        }

    async def create_tenant(
        self,
        name: str,
        contact_email: str,
        contact_phone: Optional[str] = None,
        plan: str = "free",
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        admin_username: Optional[str] = None,
        admin_email: Optional[str] = None,
        admin_password: Optional[str] = None
    ) -> dict:
        """创建租户"""
        existing = await self.tenant_repo.get_by_email(contact_email)
        if existing:
            raise ValueError("该邮箱已被使用")

        tenant = Tenant(
            name=name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            plan=plan,
            extra_metadata=metadata or {}
        )

        created = await self.tenant_repo.create(tenant)

        created_workspace = None
        created_dataset = None

        # 创建初始管理员账号
        admin_user = None
        if admin_username and admin_email and admin_password:
            user_service = UserServiceImpl(self.session)
            admin_user = await user_service.create_user(
                tenant_id=created.id,
                username=admin_username,
                email=admin_email,
                password=admin_password,
                is_active=True,
                default_role="admin"
            )

        # 创建默认工作空间（在事务中）
        workspace_service = WorkspaceServiceImpl(self.session)
        admin_user_id = (
            admin_user.get("id") if isinstance(admin_user, dict) else admin_user.id
        ) if admin_user else user_id
        created_workspace = await workspace_service.create_workspace(
            tenant_id=created.id,
            name="默认工作空间",
            creator_id=admin_user_id,
            description="系统默认创建的工作空间",
            metadata={"is_default": True},
            is_default=True
        )

        # 创建公共知识库（在事务中）
        dataset_service = DatasetServiceImpl(self.session)
        created_dataset = await dataset_service.create_dataset(
            workspace_id=UUID(created_workspace["id"]),
            name="公共知识库",
            description="租户公共知识库，包含系统默认文档",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
            metadata={"is_public": True},
            is_public=True
        )

        # 初始化文档复制状态记录
        copy_status = DocumentCopyStatus(
            dataset_id=str(created_dataset["id"]),
            status="pending",
            total_documents=0,
            completed_documents=0,
            failed_documents=0
        )
        self.session.add(copy_status)

        await self.session.flush()

        await self.audit_service.log(
            action=AuditAction.TENANT_CREATE,
            tenant_id=str(created.id),
            user_id=str(user_id) if user_id else None,
            resource_type="tenant",
            resource_id=str(created.id),
            details={"name": name, "plan": plan, "contact_email": contact_email},
            ip_address=ip_address
        )

        # 异步复制模板文档（在事务外，不阻塞租户创建返回）
        task_id = None
        if created_workspace and created_dataset:
            copy_service = DocumentCopyServiceImpl(self.session)
            template_ws = await copy_service.get_system_template_workspace()
            if not template_ws:
                logger.error("系统模板工作空间不存在，请先运行 python scripts/init_db.py")
                raise RuntimeError("系统配置错误：缺少系统模板工作空间")

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    from infrastructure.queue.document_tasks import copy_template_documents_task
                    task = copy_template_documents_task.delay(
                        str(created_workspace["id"]),
                        str(created_dataset["id"])
                    )
                    task_id = task.id
                    logger.info(f"文档复制任务已投入队列: task_id={task_id}")
                    break
                except Exception as e:
                    logger.warning(f"投入文档复制任务失败 (attempt {attempt+1}/{max_retries}): {e}")
                    if attempt == max_retries - 1:
                        logger.error(f"无法投入文档复制任务: {e}")

        # 构建配额和使用情况数据
        plan_val = created.plan.value if hasattr(created.plan, 'value') else created.plan
        quotas = self._get_quota_limits(plan_val)
        
        # 转换配额字段名
        quota_data = {
            "max_workspaces": quotas["max_workspaces"],
            "max_users": quotas["max_users"],
            "max_datasets": quotas["max_datasets"],
            "max_documents": quotas["max_documents"],
            "max_storage_gb": quotas["max_storage_mb"] // 1024 if quotas["max_storage_mb"] > 0 else 0,
            "max_api_calls_per_day": quotas["max_api_calls_per_day"]
        }
        
        # 初始使用情况都是0
        usage_data = {
            "workspace_count": 0,
            "user_count": 0,
            "dataset_count": 0,
            "document_count": 0,
            "storage_used_gb": 0,
            "api_calls_today": 0
        }

        return {
            "id": str(created.id),
            "name": created.name,
            "contact_email": created.contact_email,
            "contact_phone": created.contact_phone,
            "plan": plan_val,
            "status": created.status.value if hasattr(created.status, 'value') else created.status,
            "quota": quota_data,
            "usage": usage_data,
            "metadata": created.extra_metadata,
            "document_copy_task_id": task_id,
            "created_at": created.created_at.isoformat() if created.created_at else None,
            "updated_at": created.updated_at.isoformat() if created.updated_at else None
        }

    async def get_tenant(self, tenant_id: UUID) -> Optional[dict]:
        """获取租户详情"""
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            return None

        # 构建配额和使用情况数据
        plan_val = tenant.plan.value if hasattr(tenant.plan, 'value') else tenant.plan
        quotas = self._get_quota_limits(plan_val)
        usage = await self._get_current_usage(tenant_id)
        
        # 转换配额字段名
        quota_data = {
            "max_workspaces": quotas["max_workspaces"],
            "max_users": quotas["max_users"],
            "max_datasets": quotas["max_datasets"],
            "max_documents": quotas["max_documents"],
            "max_storage_gb": quotas["max_storage_mb"] // 1024 if quotas["max_storage_mb"] > 0 else 0,
            "max_api_calls_per_day": quotas["max_api_calls_per_day"]
        }
        
        # 转换使用情况字段名
        usage_data = {
            "workspace_count": usage["workspace_count"],
            "user_count": usage["user_count"],
            "dataset_count": usage["dataset_count"],
            "document_count": usage["document_count"],
            "storage_used_gb": usage["storage_mb"] / 1024,
            "api_calls_today": 0
        }
        
        # 获取租户的初始管理员信息
        admin_result = await self.session.execute(
            select(User).where(
                User.tenant_id == str(tenant_id),
                User.username.ilike("%admin%")
            ).limit(1)
        )
        admin_user = admin_result.scalar_one_or_none()
        admin_info = {
            "id": str(admin_user.id) if admin_user else "",
            "username": admin_user.username if admin_user else "",
            "email": admin_user.email if admin_user else ""
        } if admin_user else None

        return {
            "id": str(tenant.id),
            "name": tenant.name,
            "contact_email": tenant.contact_email,
            "contact_phone": tenant.contact_phone,
            "plan": plan_val,
            "status": tenant.status.value if hasattr(tenant.status, 'value') else tenant.status,
            "quota": quota_data,
            "usage": usage_data,
            "admin_info": admin_info,
            "metadata": tenant.extra_metadata,
            "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
            "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None
        }

    async def update_tenant(
        self,
        tenant_id: UUID,
        name: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,
        plan: Optional[str] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None
    ) -> dict:
        """更新租户"""
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise ValueError("租户不存在")

        old_values = {
            "name": tenant.name,
            "contact_email": tenant.contact_email,
            "plan": tenant.plan.value if hasattr(tenant.plan, 'value') else tenant.plan,
            "status": tenant.status.value if hasattr(tenant.status, 'value') else tenant.status,
        }

        if name is not None:
            tenant.name = name
        if contact_email is not None:
            tenant.contact_email = contact_email
        if contact_phone is not None:
            tenant.contact_phone = contact_phone
        if plan is not None:
            tenant.plan = plan
        if status is not None:
            tenant.status = status
        if metadata is not None:
            tenant.extra_metadata = metadata

        updated = await self.tenant_repo.update(tenant)

        await self.audit_service.log_data_change(
            action=AuditAction.TENANT_UPDATE,
            resource_type="tenant",
            resource_id=str(tenant_id),
            user_id=str(user_id) if user_id else None,
            tenant_id=str(tenant_id),
            old_value=old_values,
            new_value={
                "name": updated.name,
                "contact_email": updated.contact_email,
                "plan": updated.plan.value if hasattr(updated.plan, 'value') else updated.plan,
                "status": updated.status.value if hasattr(updated.status, 'value') else updated.status,
            },
            ip_address=ip_address
        )

        # 构建配额和使用情况数据
        plan_val = updated.plan.value if hasattr(updated.plan, 'value') else updated.plan
        quotas = self._get_quota_limits(plan_val)
        usage = await self._get_current_usage(tenant_id)
        
        # 转换配额字段名
        quota_data = {
            "max_workspaces": quotas["max_workspaces"],
            "max_users": quotas["max_users"],
            "max_datasets": quotas["max_datasets"],
            "max_documents": quotas["max_documents"],
            "max_storage_gb": quotas["max_storage_mb"] // 1024 if quotas["max_storage_mb"] > 0 else 0,
            "max_api_calls_per_day": quotas["max_api_calls_per_day"]
        }
        
        # 转换使用情况字段名
        usage_data = {
            "workspace_count": usage["workspace_count"],
            "user_count": usage["user_count"],
            "dataset_count": usage["dataset_count"],
            "document_count": usage["document_count"],
            "storage_used_gb": usage["storage_mb"] / 1024,
            "api_calls_today": 0
        }

        return {
            "id": str(updated.id),
            "name": updated.name,
            "contact_email": updated.contact_email,
            "contact_phone": updated.contact_phone,
            "plan": plan_val,
            "status": updated.status.value if hasattr(updated.status, 'value') else updated.status,
            "quota": quota_data,
            "usage": usage_data,
            "metadata": updated.extra_metadata,
            "created_at": updated.created_at.isoformat() if updated.created_at else None,
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None
        }

    async def delete_tenant(
        self,
        tenant_id: UUID,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None
    ) -> bool:
        """删除租户（真删除，清理所有关联数据）"""
        from pathlib import Path
        from sqlalchemy import delete, select
        from infrastructure.database.models import (
            User, Workspace, Dataset, Document, DocumentChunk, DocumentCopyStatus,
            Conversation, Message, WorkspaceMember, QuotaOverride, OpsOperation
        )

        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            return False

        tenant_key = str(tenant_id)
        logger.info(f"开始真删除租户: {tenant_key}")

        try:
            deleted_workspace_ids = []
            deleted_dataset_ids = []
            deleted_document_ids = []
            deleted_user_ids = []

            workspaces_result = await self.session.execute(
                select(Workspace).where(Workspace.tenant_id == tenant_key)
            )
            workspaces = workspaces_result.scalars().all()
            for ws in workspaces:
                deleted_workspace_ids.append(str(ws.id))

            datasets_result = await self.session.execute(
                select(Dataset).join(Workspace).where(Workspace.tenant_id == tenant_key)
            )
            datasets = datasets_result.scalars().all()
            for ds in datasets:
                deleted_dataset_ids.append(str(ds.id))

            if deleted_dataset_ids:
                docs_result = await self.session.execute(
                    select(Document).where(Document.dataset_id.in_(deleted_dataset_ids))
                )
                documents = docs_result.scalars().all()
                for doc in documents:
                    deleted_document_ids.append(str(doc.id))

                file_paths = [doc.file_path for doc in documents if doc.file_path]
                for file_path in file_paths:
                    try:
                        path = Path(file_path)
                        if path.exists():
                            path.unlink()
                            logger.info(f"已删除文件: {file_path}")
                    except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as e:
                        logger.warning(f"删除文件失败 {file_path}: {e}")

            users_result = await self.session.execute(
                select(User).where(User.tenant_id == tenant_key)
            )
            users = users_result.scalars().all()
            for user in users:
                deleted_user_ids.append(str(user.id))

            for ws_id in deleted_workspace_ids:
                await self._delete_workspace_vectors(ws_id)

            for ds_id in deleted_dataset_ids:
                await self._revoke_dataset_tasks(ds_id)

            await self.session.execute(
                delete(QuotaOverride).where(QuotaOverride.tenant_id == tenant_key)
            )
            await self.session.execute(
                delete(OpsOperation).where(OpsOperation.tenant_id == tenant_key)
            )

            await self.audit_service.log(
                action=AuditAction.TENANT_DELETE,
                tenant_id=str(tenant_id),
                user_id=str(user_id) if user_id else None,
                resource_type="tenant",
                resource_id=str(tenant_id),
                details={
                    "name": tenant.name,
                    "deleted_users": len(deleted_user_ids),
                    "deleted_workspaces": len(deleted_workspace_ids),
                    "deleted_datasets": len(deleted_dataset_ids),
                    "deleted_documents": len(deleted_document_ids)
                },
                ip_address=ip_address
            )

            # Use a direct DELETE so PostgreSQL performs the configured
            # ON DELETE CASCADE without SQLAlchemy loading legacy optional
            # relationships (OAuth/audit tables may not exist or may use
            # older identifier types in production).
            await self.session.execute(delete(Tenant).where(Tenant.id == tenant_id))
            await self.session.flush()

            logger.info(
                f"租户删除完成: tenant={tenant_key}, "
                f"users={len(deleted_user_ids)}, workspaces={len(deleted_workspace_ids)}, "
                f"datasets={len(deleted_dataset_ids)}, documents={len(deleted_document_ids)}"
            )
            return True

        except (SQLAlchemyError, RuntimeError, ValueError, TypeError, OSError, AttributeError) as e:
            logger.error(f"删除租户失败: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def _delete_workspace_vectors(self, workspace_id: str) -> None:
        """删除工作空间的向量数据"""
        try:
            collection_name = f"enterprise_rag_{workspace_id.replace('-', '_')}"
            from core.rag.vector_store import create_vector_store, VectorStore
            from core.rag.embedding import get_embedding_service

            embedding_service = get_embedding_service()
            vector_store = await create_vector_store(
                collection_name=collection_name,
                embedding_service=embedding_service,
                use_memory_fallback=False
            )

            if isinstance(vector_store, VectorStore):
                client = await vector_store._get_client()
                response = await client.delete(
                    f"{vector_store.config.qdrant_url}/collections/{collection_name}/points/delete",
                    json={"filter": {}}
                )
                if response.status_code == 200:
                    logger.info(f"已删除工作空间向量集合: {collection_name}")
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"删除工作空间向量数据失败 workspace_id={workspace_id}: {e}")

    async def _revoke_dataset_tasks(self, dataset_id: str) -> None:
        """取消数据集相关的待处理任务"""
        try:
            await self.session.execute(
                delete(DocumentCopyStatus).where(DocumentCopyStatus.dataset_id == dataset_id)
            )
            logger.info(f"已清理数据集任务状态: {dataset_id}")
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"清理数据集任务失败 dataset_id={dataset_id}: {e}")

    async def list_tenants(
        self,
        status: Optional[str] = None,
        plan: Optional[str] = None,
        keyword: Optional[str] = None,
        pagination: Optional[Pagination] = None
    ) -> Page:
        """查询租户列表"""
        filters = {}
        # 默认不显示已删除的租户
        if status:
            filters["status"] = status
        else:
            filters["status"] = "active"
        if plan:
            filters["plan"] = plan

        result = await self.tenant_repo.list(filters, pagination)

        items = []
        for tenant in result.items:
            tenant_id = tenant.get("id") if isinstance(tenant, dict) else tenant.id
            plan_raw = tenant.get("plan") if isinstance(tenant, dict) else tenant.plan
            status_raw = tenant.get("status") if isinstance(tenant, dict) else tenant.status
            plan_val = _normalize_enum_value(plan_raw, "free")
            status_val = _normalize_enum_value(status_raw, "active")

            # 构建配额和使用情况数据
            quotas = self._get_quota_limits(plan_val)
            usage = await self._get_current_usage(UUID(str(tenant_id)))
            
            # 转换配额字段名
            quota_data = {
                "max_workspaces": quotas["max_workspaces"],
                "max_users": quotas["max_users"],
                "max_datasets": quotas["max_datasets"],
                "max_documents": quotas["max_documents"],
                "max_storage_gb": quotas["max_storage_mb"] // 1024 if quotas["max_storage_mb"] > 0 else 0,
                "max_api_calls_per_day": quotas["max_api_calls_per_day"]
            }
            
            # 转换使用情况字段名
            usage_data = {
                "workspace_count": usage["workspace_count"],
                "user_count": usage["user_count"],
                "dataset_count": usage["dataset_count"],
                "document_count": usage["document_count"],
                "storage_used_gb": usage["storage_mb"] / 1024,
                "api_calls_today": 0
            }
            
            # 获取租户的初始管理员信息
            admin_result = await self.session.execute(
                select(User).where(
                    User.tenant_id == str(tenant_id),
                    User.username.ilike("%admin%")
                ).limit(1)
            )
            admin_user = admin_result.scalar_one_or_none()
            admin_info = {
                "id": str(admin_user.id) if admin_user else "",
                "username": admin_user.username if admin_user else "",
                "email": admin_user.email if admin_user else ""
            } if admin_user else None

            items.append({
                "id": str(tenant_id),
                "name": tenant.get("name") if isinstance(tenant, dict) else tenant.name,
                "contact_email": tenant.get("contact_email") if isinstance(tenant, dict) else tenant.contact_email,
                "contact_phone": tenant.get("contact_phone") if isinstance(tenant, dict) else tenant.contact_phone,
                "plan": plan_val,
                "status": status_val,
                "admin_info": admin_info,
                "quota": quota_data,
                "usage": usage_data,
                "metadata": _normalize_metadata(
                    tenant.get("extra_metadata") if isinstance(tenant, dict) else tenant.extra_metadata
                ),
                "created_at": _to_iso_datetime(tenant.get("created_at") if isinstance(tenant, dict) else tenant.created_at),
                "updated_at": _to_iso_datetime(tenant.get("updated_at") if isinstance(tenant, dict) else tenant.updated_at),
            })

        return Page(
            items=items,
            total=result.total,
            page=result.page,
            page_size=result.page_size
        )

    async def get_tenant_usage(self, tenant_id: UUID) -> dict:
        """获取租户使用情况"""
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise ValueError("租户不存在")

        usage = await self._get_current_usage(tenant_id)
        quota_status = await self.get_quota_status(tenant_id)

        return {
            "tenant_id": str(tenant_id),
            "usage": usage,
            "quota_status": quota_status
        }
