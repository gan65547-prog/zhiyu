import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


class OperationService:
    """运维操作服务：幂等、状态流转、审计补充。"""

    def __init__(self, db):
        self.db = db

    async def get_by_operation_id(self, operation_id: str) -> Optional[dict]:
        row = await self.db.fetch_one(
            """
            SELECT * FROM ops_operations
            WHERE operation_id = :operation_id
            LIMIT 1
            """,
            {"operation_id": operation_id},
        )
        return dict(row) if row else None

    async def create_pending_operation(
        self,
        operation_id: str,
        operator_name: str,
        action: str,
        target_env: str,
        target_service: str,
        tenant_id: Optional[str],
        request_payload: dict[str, Any],
        source_ip: Optional[str],
        operator_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        before_snapshot: Optional[dict[str, Any]] = None,
    ) -> dict:
        existing = await self.get_by_operation_id(operation_id)
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        op_id = str(uuid4())
        await self.db.execute(
            """
            INSERT INTO ops_operations (
                id, operation_id, operator_id, operator_name, target_env, target_service,
                tenant_id, action, resource_type, resource_id, request_payload,
                before_snapshot, status, source_ip, created_at, updated_at
            )
            VALUES (
                :id, :operation_id, :operator_id, :operator_name, :target_env, :target_service,
                :tenant_id, :action, :resource_type, :resource_id, :request_payload,
                :before_snapshot, 'PENDING', :source_ip, :created_at, :updated_at
            )
            """,
            {
                "id": op_id,
                "operation_id": operation_id,
                "operator_id": operator_id,
                "operator_name": operator_name,
                "target_env": target_env,
                "target_service": target_service,
                "tenant_id": tenant_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "request_payload": json.dumps(request_payload, ensure_ascii=False),
                "before_snapshot": json.dumps(before_snapshot, ensure_ascii=False) if before_snapshot else None,
                "source_ip": source_ip,
                "created_at": now,
                "updated_at": now,
            },
        )
        return await self.get_by_operation_id(operation_id)

    async def mark_succeeded(self, operation_id: str, after_snapshot: Optional[dict[str, Any]] = None) -> None:
        await self.db.execute(
            """
            UPDATE ops_operations
            SET status = 'SUCCEEDED',
                after_snapshot = :after_snapshot,
                finished_at = :finished_at,
                updated_at = :updated_at
            WHERE operation_id = :operation_id
            """,
            {
                "operation_id": operation_id,
                "after_snapshot": json.dumps(after_snapshot, ensure_ascii=False) if after_snapshot else None,
                "finished_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )

    async def mark_failed(self, operation_id: str, error_message: str) -> None:
        await self.db.execute(
            """
            UPDATE ops_operations
            SET status = 'FAILED',
                error_message = :error_message,
                finished_at = :finished_at,
                updated_at = :updated_at
            WHERE operation_id = :operation_id
            """,
            {
                "operation_id": operation_id,
                "error_message": error_message[:2000],
                "finished_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )

    async def mark_running(self, operation_id: str) -> None:
        await self.db.execute(
            """
            UPDATE ops_operations
            SET status = 'RUNNING',
                updated_at = :updated_at
            WHERE operation_id = :operation_id
            """,
            {
                "operation_id": operation_id,
                "updated_at": datetime.now(timezone.utc),
            },
        )

    async def create_task_event(
        self,
        operation_id: str,
        task_id: str,
        event_type: str,
        message: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
        retry_count: int = 0,
        error_code: Optional[str] = None,
    ) -> None:
        await self.db.execute(
            """
            INSERT INTO ops_task_events (
                id, operation_id, task_id, event_type, message, payload, retry_count, error_code, created_at
            )
            VALUES (
                :id, :operation_id, :task_id, :event_type, :message, :payload, :retry_count, :error_code, :created_at
            )
            """,
            {
                "id": str(uuid4()),
                "operation_id": operation_id,
                "task_id": task_id,
                "event_type": event_type,
                "message": message,
                "payload": json.dumps(payload or {}, ensure_ascii=False),
                "retry_count": retry_count,
                "error_code": error_code,
                "created_at": datetime.now(timezone.utc),
            },
        )

    async def write_audit_log(
        self,
        action: str,
        tenant_id: Optional[str],
        resource_type: str,
        resource_id: Optional[str],
        details: dict[str, Any],
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> None:
        """不阻断主流程的审计补充写入。"""
        try:
            await self.db.execute(
                """
                INSERT INTO audit_logs (
                    id, action, resource_type, resource_id, user_id, tenant_id,
                    workspace_id, ip_address, user_agent, details, status, error_message, created_at
                )
                VALUES (
                    :id, :action, :resource_type, :resource_id, :user_id, :tenant_id,
                    NULL, NULL, NULL, :details, :status, :error_message, :created_at
                )
                """,
                {
                    "id": str(uuid4()),
                    "action": action,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "user_id": None,
                    "tenant_id": tenant_id,
                    "details": json.dumps(details, ensure_ascii=False),
                    "status": status,
                    "error_message": error_message,
                    "created_at": datetime.now(timezone.utc),
                },
            )
        except Exception:
            return

