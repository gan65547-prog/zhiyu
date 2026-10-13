"""显式 Agent 工作流运行时。

运行时只编排已登记的步骤，不接受任意 Python/工具代码。研究运行通过本服务
创建对应的 agent_run，研究业务状态仍由 ResearchRun 负责。
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models import AgentApproval, AgentDefinition, AgentOutput, AgentRun, AgentRunStep, AgentSchedule, ResearchProject, ResearchReport, ResearchRun
from core.workflow_contracts import workflow_contains_required_steps
from services.impl.asset_service import AssetServiceImpl
from services.impl.agent_tool_registry import AgentTool, AgentToolRegistry


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


RESEARCH_WORKFLOW = [
    {"key": "collect_sources", "label": "收集来源"},
    {"key": "build_evidence", "label": "整理证据"},
    {"key": "synthesize_findings", "label": "综合发现"},
    {"key": "generate_report", "label": "生成报告"},
    {"key": "human_review", "label": "人工审核"},
]
ASSET_ORGANIZE_WORKFLOW = [
    {"key": "read_material", "label": "读取素材"},
    {"key": "summarize", "label": "生成摘要"},
    {"key": "extract_tags", "label": "提取标签"},
    {"key": "propose_knowledge", "label": "生成知识草稿"},
    {"key": "human_review", "label": "人工审核"},
]
ALLOWED_AGENT_TYPES = {"research_analysis", "asset_organize"}


def next_schedule_time(expression: str, after: datetime) -> datetime:
    """计算首版支持的常用 cron：每 N 分钟、每小时或每天固定时刻。"""
    fields = expression.split()
    if len(fields) != 5 or fields[2:] != ["*", "*", "*"]:
        raise ValueError("首版仅支持 '* * * * *'、'*/N * * * *'、'M * * * *' 或 'M H * * *'")
    minute, hour = fields[0], fields[1]
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    if minute.startswith("*/") and hour == "*":
        interval = int(minute[2:])
        if not 1 <= interval <= 59:
            raise ValueError("分钟间隔必须在 1 到 59 之间")
        offset = (interval - candidate.minute % interval) % interval
        return candidate + timedelta(minutes=offset)
    if minute.isdigit() and hour == "*" and 0 <= int(minute) <= 59:
        return candidate.replace(minute=int(minute)) + (timedelta(hours=1) if candidate.minute > int(minute) else timedelta(0))
    if minute.isdigit() and hour.isdigit() and 0 <= int(minute) <= 59 and 0 <= int(hour) <= 23:
        result = candidate.replace(hour=int(hour), minute=int(minute))
        return result if result > after else result + timedelta(days=1)
    raise ValueError("无效的调度表达式")


class AgentRuntimeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.access = AssetServiceImpl(session)
        self.tools = AgentToolRegistry()

    async def _verify_access(self, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> None:
        await self.access._verify_workspace_access(workspace_id, tenant_id, user_id, is_superuser)

    @staticmethod
    def _validate_workflow(workflow: list[dict[str, Any]], tools: AgentToolRegistry | None = None) -> None:
        keys = [str(step.get("key", "")) for step in workflow]
        if not keys or any(not key for key in keys) or len(set(keys)) != len(keys):
            raise ValueError("Agent 工作流必须包含唯一的步骤 key")
        for step in workflow:
            tool_key = step.get("tool")
            if tool_key is not None and (tools is None or tools.get(str(tool_key)) is None):
                raise ValueError(f"工作流引用了未注册的 Agent 工具: {tool_key}")
            if "tool" in step and not isinstance(step.get("input"), dict):
                raise ValueError("Agent 工具步骤的 input 必须是 JSON 对象")

    async def ensure_research_definition(self, *, tenant_id: UUID, workspace_id: UUID, user_id: UUID) -> AgentDefinition:
        result = await self.session.execute(
            select(AgentDefinition).where(
                AgentDefinition.tenant_id == str(tenant_id), AgentDefinition.workspace_id == str(workspace_id),
                AgentDefinition.agent_type == "research_analysis", AgentDefinition.status == "active",
            ).order_by(AgentDefinition.created_at.asc())
        )
        definitions = result.scalars().all()
        definition = next((item for item in definitions if workflow_contains_required_steps(item.workflow, RESEARCH_WORKFLOW)), None)
        if definition:
            return definition
        definition = AgentDefinition(
            tenant_id=str(tenant_id), workspace_id=str(workspace_id), created_by=str(user_id),
            name="研究分析工作流", agent_type="research_analysis", description="研究来源到报告的显式可审计工作流",
            workflow=RESEARCH_WORKFLOW, status="active", created_at=_utcnow(), updated_at=_utcnow(),
        )
        self.session.add(definition)
        await self.session.flush()
        return definition

    async def ensure_asset_organize_definition(self, *, tenant_id: UUID, workspace_id: UUID, user_id: UUID) -> AgentDefinition:
        result = await self.session.execute(select(AgentDefinition).where(AgentDefinition.tenant_id == str(tenant_id), AgentDefinition.workspace_id == str(workspace_id), AgentDefinition.agent_type == "asset_organize", AgentDefinition.status == "active").order_by(AgentDefinition.created_at.asc()))
        definitions = result.scalars().all()
        definition = next((item for item in definitions if workflow_contains_required_steps(item.workflow, ASSET_ORGANIZE_WORKFLOW)), None)
        if definition:
            return definition
        definition = AgentDefinition(tenant_id=str(tenant_id), workspace_id=str(workspace_id), created_by=str(user_id), name="素材整理与知识提炼", agent_type="asset_organize", description="从已解析素材生成带证据的知识草稿", workflow=ASSET_ORGANIZE_WORKFLOW, status="active", created_at=_utcnow(), updated_at=_utcnow())
        self.session.add(definition)
        await self.session.flush()
        return definition

    async def create_definition(self, *, tenant_id: UUID, user_id: UUID, is_superuser: bool, data: dict[str, Any]) -> dict[str, Any]:
        workspace_id = UUID(str(data["workspace_id"]))
        await self._verify_access(workspace_id, tenant_id, user_id, is_superuser)
        agent_type = str(data["agent_type"])
        if agent_type not in ALLOWED_AGENT_TYPES:
            raise ValueError("当前只支持 research_analysis 或 asset_organize Agent 类型")
        workflow = data.get("workflow") or (ASSET_ORGANIZE_WORKFLOW if agent_type == "asset_organize" else RESEARCH_WORKFLOW)
        self._validate_workflow(workflow, self.tools)
        definition = AgentDefinition(
            tenant_id=str(tenant_id), workspace_id=str(workspace_id), created_by=str(user_id),
            name=str(data["name"]).strip(), agent_type=agent_type, description=data.get("description"),
            workflow=workflow, status="active", created_at=_utcnow(), updated_at=_utcnow(),
        )
        self.session.add(definition)
        await self.session.flush()
        return self._definition_dict(definition)

    def list_tools(self) -> list[dict[str, Any]]:
        """返回可供前端展示的工具能力，不暴露可执行代码。"""
        return self.tools.describe()

    async def create_run(self, *, tenant_id: UUID, user_id: UUID, is_superuser: bool, data: dict[str, Any]) -> dict[str, Any]:
        workspace_id = UUID(str(data["workspace_id"]))
        await self._verify_access(workspace_id, tenant_id, user_id, is_superuser)
        definition = await self.session.scalar(select(AgentDefinition).where(
            AgentDefinition.id == str(data["definition_id"]), AgentDefinition.tenant_id == str(tenant_id),
            AgentDefinition.workspace_id == str(workspace_id), AgentDefinition.status == "active",
        ))
        if definition is None:
            raise ValueError("Agent 定义不存在或不属于当前工作空间")
        workflow = definition.workflow or []
        self._validate_workflow(workflow, self.tools)
        run = AgentRun(
            tenant_id=str(tenant_id), workspace_id=str(workspace_id), definition_id=definition.id,
            created_by=str(user_id), status="queued", input_json=data.get("input") or {},
            config_json=data.get("config") or {}, created_at=_utcnow(), updated_at=_utcnow(),
        )
        self.session.add(run)
        await self.session.flush()
        for order, step in enumerate(workflow, 1):
            self.session.add(AgentRunStep(
                tenant_id=str(tenant_id), workspace_id=str(workspace_id), agent_run_id=run.id,
                step_key=step["key"], step_order=order, status="pending", input_json=step.get("input") or {},
                output_json={}, created_at=_utcnow(), updated_at=_utcnow(),
            ))
        await self.session.flush()
        return await self.get_run(agent_run_id=run.id, tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser)

    async def execute_tool_step(
        self, *, agent_run_id: UUID, step_key: str, arguments: dict[str, Any],
        tenant_id: UUID, user_id: UUID, is_superuser: bool,
    ) -> dict[str, Any] | None:
        context = await self._load_tool_context(agent_run_id, step_key, tenant_id, user_id, is_superuser)
        if context is None:
            return None
        run, step, tool = context
        # 在创建审批记录前保存本次调用参数，审批通过后才能无损恢复执行。
        step.input_json = arguments or {}
        approval = await self._tool_approval(run, step, tool.requires_approval)
        if approval is not None and approval.status != "approved":
            return self._tool_response(run, step_key, tool, "waiting_approval", approval, {})
        if step.status == "completed":
            return self._tool_response(run, step_key, tool, step.status, approval, step.output_json or {})
        run.status, run.current_step, run.started_at = "running", step_key, run.started_at or _utcnow()
        return await self._execute_registered_tool(run, step, tool, arguments, approval)

    async def _load_tool_context(self, agent_run_id: UUID, step_key: str, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> tuple[AgentRun, AgentRunStep, AgentTool] | None:
        run = await self.session.scalar(select(AgentRun).where(AgentRun.id == str(agent_run_id), AgentRun.tenant_id == str(tenant_id)))
        if run is None:
            return None
        await self._verify_access(UUID(str(run.workspace_id)), tenant_id, user_id, is_superuser)
        definition = await self.session.get(AgentDefinition, str(run.definition_id))
        step = await self.session.scalar(select(AgentRunStep).where(AgentRunStep.agent_run_id == str(run.id), AgentRunStep.step_key == step_key))
        workflow_step = self._workflow_step(definition.workflow if definition else [], step_key)
        tool = self.tools.get(str(workflow_step.get("tool") or ""))
        if step is None or tool is None:
            raise ValueError("步骤不存在或未绑定已注册工具")
        return run, step, tool

    @staticmethod
    def _tool_response(run: AgentRun, step_key: str, tool: AgentTool, status: str, approval: AgentApproval | None, output: dict[str, Any]) -> dict[str, Any]:
        return {"run_id": run.id, "step_key": step_key, "tool": tool.key, "status": status, "approval_id": approval.id if approval else None, "output": output}

    async def _execute_registered_tool(self, run: AgentRun, step: AgentRunStep, tool: AgentTool, arguments: dict[str, Any], approval: AgentApproval | None) -> dict[str, Any]:
        try:
            await self.mark_step(agent_run_id=run.id, step_key=step.step_key, status="running")
            output = await self.tools.execute(tool.key, arguments)
            await self.mark_step(agent_run_id=run.id, step_key=step.step_key, status="completed", output=output)
            run.progress = await self._run_progress(run.id)
            run.status = "completed" if run.progress == 100 else "running"
            if run.status == "completed":
                run.completed_at = _utcnow()
            await self.session.flush()
            return self._tool_response(run, step.step_key, tool, "completed", approval, output)
        except Exception as exc:
            error_message = str(exc)[:2000]
            await self.mark_step(agent_run_id=run.id, step_key=step.step_key, status="failed", error=error_message)
            run.status, run.error_message, run.current_step = "failed", error_message, step.step_key
            await self.session.flush()
            # 工具失败是可审计的业务终态，必须作为正常响应提交，避免路由层
            # 回滚掉失败记录，前端才能展示错误并提供重试入口。
            return self._tool_response(run, step.step_key, tool, "failed", approval, {"error": error_message})

    @staticmethod
    def _workflow_step(workflow: list[dict[str, Any]], step_key: str) -> dict[str, Any]:
        return next((step for step in workflow if str(step.get("key")) == step_key), {})

    async def _tool_approval(self, run: AgentRun, step: AgentRunStep, requires_approval: bool) -> AgentApproval | None:
        if not requires_approval:
            return None
        approval = await self.session.scalar(select(AgentApproval).where(
            AgentApproval.agent_run_id == str(run.id), AgentApproval.step_id == str(step.id),
        ).order_by(AgentApproval.created_at.desc()).limit(1))
        if approval is not None:
            return approval
        approval = await self.request_approval(agent_run_id=run.id, step_key=step.step_key)
        run.status, run.current_step = "waiting_approval", step.step_key
        step.status = "waiting_approval"
        await self.session.flush()
        return approval

    async def _run_progress(self, agent_run_id: UUID) -> int:
        steps = list((await self.session.execute(select(AgentRunStep.status).where(AgentRunStep.agent_run_id == str(agent_run_id)))).scalars())
        return int(sum(status == "completed" for status in steps) * 100 / max(1, len(steps)))

    @staticmethod
    def _definition_dict(definition: AgentDefinition) -> dict[str, Any]:
        return {
            "id": definition.id, "workspace_id": definition.workspace_id, "name": definition.name,
            "agent_type": definition.agent_type, "description": definition.description, "version": definition.version,
            "workflow": definition.workflow or [], "status": definition.status,
            "created_at": definition.created_at, "updated_at": definition.updated_at,
        }

    async def list_definitions(self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> list[dict[str, Any]]:
        await self._verify_access(workspace_id, tenant_id, user_id, is_superuser)
        result = await self.session.execute(
            select(AgentDefinition).where(AgentDefinition.workspace_id == str(workspace_id), AgentDefinition.tenant_id == str(tenant_id), AgentDefinition.status == "active").order_by(AgentDefinition.created_at.asc())
        )
        return [self._definition_dict(item) for item in result.scalars().all()]

    async def create_research_run(self, *, research_run: ResearchRun, user_id: UUID) -> AgentRun:
        definition = await self.ensure_research_definition(
            tenant_id=UUID(str(research_run.tenant_id)), workspace_id=UUID(str(research_run.workspace_id)), user_id=user_id,
        )
        agent_run = AgentRun(
            tenant_id=research_run.tenant_id, workspace_id=research_run.workspace_id, definition_id=definition.id,
            research_run_id=research_run.id, created_by=str(user_id), status="queued",
            input_json={"research_run_id": str(research_run.id)}, config_json={}, created_at=_utcnow(), updated_at=_utcnow(),
        )
        self.session.add(agent_run)
        await self.session.flush()
        for order, step in enumerate(definition.workflow or [], 1):
            self.session.add(AgentRunStep(
                tenant_id=research_run.tenant_id, workspace_id=research_run.workspace_id, agent_run_id=agent_run.id,
                step_key=step["key"], step_order=order, status="pending", input_json={}, output_json={},
                created_at=_utcnow(), updated_at=_utcnow(),
            ))
        await self.session.flush()
        return agent_run

    async def create_asset_organize_run(self, *, asset_id: UUID, tenant_id: UUID, workspace_id: UUID, user_id: UUID) -> AgentRun:
        definition = await self.ensure_asset_organize_definition(tenant_id=tenant_id, workspace_id=workspace_id, user_id=user_id)
        agent_run = AgentRun(tenant_id=str(tenant_id), workspace_id=str(workspace_id), definition_id=definition.id, created_by=str(user_id), status="queued", input_json={"asset_id": str(asset_id)}, config_json={}, created_at=_utcnow(), updated_at=_utcnow())
        self.session.add(agent_run)
        await self.session.flush()
        for order, step in enumerate(definition.workflow or [], 1):
            self.session.add(AgentRunStep(tenant_id=str(tenant_id), workspace_id=str(workspace_id), agent_run_id=agent_run.id, step_key=step["key"], step_order=order, status="pending", input_json={}, output_json={}, created_at=_utcnow(), updated_at=_utcnow()))
        await self.session.flush()
        return agent_run

    async def mark_step(self, *, agent_run_id: UUID, step_key: str, status: str, output: Optional[dict[str, Any]] = None, error: Optional[str] = None) -> None:
        result = await self.session.execute(
            select(AgentRunStep).where(AgentRunStep.agent_run_id == str(agent_run_id), AgentRunStep.step_key == step_key)
        )
        step = result.scalar_one_or_none()
        if step is None:
            raise LookupError("Agent 步骤不存在")
        step.status = status
        if output is not None:
            step.output_json = output
            self.session.add(AgentOutput(
                tenant_id=step.tenant_id, workspace_id=step.workspace_id, agent_run_id=step.agent_run_id,
                step_id=step.id, output_type="step_result", title=step.step_key,
                content_json=output, review_status="pending", created_at=_utcnow(),
            ))
        if error:
            step.error_message = error[:2000]
        if status == "running":
            step.started_at = _utcnow()
        if status in {"completed", "failed", "cancelled"}:
            step.completed_at = _utcnow()
        await self.session.flush()

    async def request_approval(self, *, agent_run_id: UUID, step_key: str) -> AgentApproval:
        step_result = await self.session.execute(
            select(AgentRunStep).where(AgentRunStep.agent_run_id == str(agent_run_id), AgentRunStep.step_key == step_key)
        )
        step = step_result.scalar_one_or_none()
        run = await self.session.get(AgentRun, str(agent_run_id))
        if step is None or run is None:
            raise LookupError("Agent 审批节点不存在")
        approval = AgentApproval(
            tenant_id=run.tenant_id, workspace_id=run.workspace_id, agent_run_id=run.id, step_id=step.id,
            status="pending", created_at=_utcnow(),
        )
        self.session.add(approval)
        await self.session.flush()
        return approval

    async def get_run(self, *, agent_run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[dict[str, Any]]:
        result = await self.session.execute(select(AgentRun).where(AgentRun.id == str(agent_run_id), AgentRun.tenant_id == str(tenant_id)))
        run = result.scalar_one_or_none()
        if run is None:
            return None
        await self._verify_access(UUID(str(run.workspace_id)), tenant_id, user_id, is_superuser)
        steps_result = await self.session.execute(select(AgentRunStep).where(AgentRunStep.agent_run_id == str(run.id)).order_by(AgentRunStep.step_order.asc()))
        return {
            "id": run.id, "research_run_id": run.research_run_id, "definition_id": run.definition_id,
            "status": run.status, "current_step": run.current_step, "progress": run.progress,
            "error_message": run.error_message, "retry_count": run.retry_count,
            "steps": [{"id": step.id, "step_key": step.step_key, "step_order": step.step_order, "status": step.status, "output_json": step.output_json or {}, "error_message": step.error_message} for step in steps_result.scalars().all()],
            "created_at": run.created_at, "updated_at": run.updated_at,
        }

    async def list_events(self, *, agent_run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[list[dict[str, Any]]]:
        result = await self.session.execute(select(AgentRun).where(AgentRun.id == str(agent_run_id), AgentRun.tenant_id == str(tenant_id)))
        run = result.scalar_one_or_none()
        if run is None:
            return None
        await self._verify_access(UUID(str(run.workspace_id)), tenant_id, user_id, is_superuser)
        steps_result = await self.session.execute(select(AgentRunStep).where(AgentRunStep.agent_run_id == str(run.id)).order_by(AgentRunStep.step_order.asc()))
        output_result = await self.session.execute(select(AgentOutput).where(AgentOutput.agent_run_id == str(run.id)).order_by(AgentOutput.created_at.asc()))
        events = [
            {"id": step.id, "event_type": "step", "step_key": step.step_key, "status": step.status,
             "title": step.step_key, "content": step.output_json or {}, "created_at": step.updated_at}
            for step in steps_result.scalars().all()
        ]
        events.extend(
            {"id": output.id, "event_type": "output", "step_key": None, "status": output.review_status,
             "title": output.title, "content": output.content_json or {}, "created_at": output.created_at}
            for output in output_result.scalars().all()
        )
        return sorted(events, key=lambda event: event["created_at"])

    async def list_runs(self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, page: int = 1, page_size: int = 20) -> dict[str, Any]:
        await self._verify_access(workspace_id, tenant_id, user_id, is_superuser)
        conditions = [AgentRun.workspace_id == str(workspace_id), AgentRun.tenant_id == str(tenant_id)]
        total = int(await self.session.scalar(select(func.count(AgentRun.id)).where(*conditions)) or 0)
        result = await self.session.execute(
            select(AgentRun).where(*conditions).order_by(AgentRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        items = []
        for run in result.scalars().all():
            item = await self.get_run(agent_run_id=UUID(str(run.id)), tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser)
            if item:
                items.append(item)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def cancel_run(self, *, agent_run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[dict[str, Any]]:
        result = await self.session.execute(select(AgentRun).where(AgentRun.id == str(agent_run_id), AgentRun.tenant_id == str(tenant_id)))
        run = result.scalar_one_or_none()
        if run is None:
            return None
        await self._verify_access(UUID(str(run.workspace_id)), tenant_id, user_id, is_superuser)
        if run.status not in {"completed", "failed", "cancelled"}:
            run.status = "cancelled"
            run.current_step = "cancelled"
            await self.session.flush()
        return await self.get_run(agent_run_id=agent_run_id, tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser)

    async def retry_run(self, *, agent_run_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> Optional[dict[str, Any]]:
        result = await self.session.execute(select(AgentRun).where(AgentRun.id == str(agent_run_id), AgentRun.tenant_id == str(tenant_id)))
        run = result.scalar_one_or_none()
        if run is None:
            return None
        await self._verify_access(UUID(str(run.workspace_id)), tenant_id, user_id, is_superuser)
        if run.status not in {"failed", "cancelled", "rejected"}:
            raise ValueError("只有失败、取消或驳回的 Agent 运行可以重试")
        run.status, run.current_step, run.progress, run.error_message = "queued", None, 0, None
        run.retry_count += 1
        if run.research_run_id:
            research_run = await self.session.get(ResearchRun, str(run.research_run_id))
            if research_run:
                research_run.status, research_run.current_stage, research_run.progress = "pending", None, 0
                research_run.error_message = None
                research_run.retry_count += 1
        steps_result = await self.session.execute(select(AgentRunStep).where(AgentRunStep.agent_run_id == str(run.id)))
        for step in steps_result.scalars().all():
            step.status, step.output_json, step.error_message = "pending", {}, None
            step.started_at, step.completed_at = None, None
            step.retry_count += 1
        await self.session.flush()
        return await self.get_run(agent_run_id=agent_run_id, tenant_id=tenant_id, user_id=user_id, is_superuser=is_superuser)

    @staticmethod
    def _schedule_dict(schedule: AgentSchedule) -> dict[str, Any]:
        return {"id": schedule.id, "workspace_id": schedule.workspace_id, "definition_id": schedule.definition_id, "project_id": schedule.project_id, "name": schedule.name, "schedule_expression": schedule.schedule_expression, "timezone": schedule.timezone, "config_json": schedule.config_json or {}, "enabled": schedule.enabled, "next_run_at": schedule.next_run_at, "last_run_at": schedule.last_run_at, "last_run_id": schedule.last_run_id, "last_error": schedule.last_error, "created_at": schedule.created_at, "updated_at": schedule.updated_at}

    async def create_schedule(self, *, tenant_id: UUID, user_id: UUID, is_superuser: bool, data: dict[str, Any]) -> dict[str, Any]:
        workspace_id, definition_id, project_id = UUID(str(data["workspace_id"])), UUID(str(data["definition_id"])), UUID(str(data["project_id"]))
        await self._verify_access(workspace_id, tenant_id, user_id, is_superuser)
        next_schedule_time(str(data["schedule_expression"]), data["next_run_at"])
        definition = await self.session.scalar(select(AgentDefinition).where(AgentDefinition.id == str(definition_id), AgentDefinition.workspace_id == str(workspace_id), AgentDefinition.tenant_id == str(tenant_id), AgentDefinition.status == "active"))
        project = await self.session.scalar(select(ResearchProject).where(ResearchProject.id == str(project_id), ResearchProject.workspace_id == str(workspace_id), ResearchProject.tenant_id == str(tenant_id), ResearchProject.deleted_at.is_(None)))
        if not definition or not project:
            raise ValueError("Agent 定义或研究项目不存在，或不属于当前工作空间")
        schedule = AgentSchedule(tenant_id=str(tenant_id), workspace_id=str(workspace_id), definition_id=str(definition_id), project_id=str(project_id), created_by=str(user_id), name=str(data["name"]).strip(), schedule_expression=str(data["schedule_expression"]).strip(), timezone=str(data.get("timezone") or "Asia/Shanghai"), config_json=data.get("config_json") or {}, enabled=True, next_run_at=data["next_run_at"], created_at=_utcnow(), updated_at=_utcnow())
        self.session.add(schedule)
        await self.session.flush()
        return self._schedule_dict(schedule)

    async def list_schedules(self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool) -> list[dict[str, Any]]:
        await self._verify_access(workspace_id, tenant_id, user_id, is_superuser)
        result = await self.session.execute(select(AgentSchedule).where(AgentSchedule.workspace_id == str(workspace_id), AgentSchedule.tenant_id == str(tenant_id)).order_by(AgentSchedule.next_run_at.asc()))
        return [self._schedule_dict(item) for item in result.scalars().all()]

    async def set_schedule_enabled(self, *, schedule_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, enabled: bool) -> Optional[dict[str, Any]]:
        schedule = await self.session.scalar(select(AgentSchedule).where(AgentSchedule.id == str(schedule_id), AgentSchedule.tenant_id == str(tenant_id)))
        if not schedule:
            return None
        await self._verify_access(UUID(str(schedule.workspace_id)), tenant_id, user_id, is_superuser)
        schedule.enabled = enabled
        schedule.updated_at = _utcnow()
        await self.session.flush()
        return self._schedule_dict(schedule)

    async def _approval_dict(self, approval: AgentApproval) -> dict[str, Any]:
        run = await self.session.get(AgentRun, str(approval.agent_run_id))
        step = await self.session.get(AgentRunStep, str(approval.step_id)) if approval.step_id else None
        return {
            "id": approval.id, "agent_run_id": approval.agent_run_id,
            "research_run_id": run.research_run_id if run else None, "step_id": approval.step_id,
            "step_key": step.step_key if step else None, "status": approval.status,
            "reviewer_id": approval.reviewer_id, "comment": approval.comment,
            "created_at": approval.created_at, "reviewed_at": approval.reviewed_at,
        }

    async def list_approvals(self, *, workspace_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, pending_only: bool = True) -> list[dict[str, Any]]:
        await self._verify_access(workspace_id, tenant_id, user_id, is_superuser)
        conditions = [AgentApproval.workspace_id == str(workspace_id), AgentApproval.tenant_id == str(tenant_id)]
        if pending_only:
            conditions.append(AgentApproval.status == "pending")
        result = await self.session.execute(select(AgentApproval).where(*conditions).order_by(AgentApproval.created_at.desc()).limit(100))
        return [await self._approval_dict(item) for item in result.scalars().all()]

    async def review_approval(self, *, approval_id: UUID, tenant_id: UUID, user_id: UUID, is_superuser: bool, status: str, comment: Optional[str] = None) -> Optional[dict[str, Any]]:
        if status not in {"approved", "rejected"}:
            raise ValueError("审批状态必须是 approved 或 rejected")
        approval = await self.session.scalar(select(AgentApproval).where(AgentApproval.id == str(approval_id), AgentApproval.tenant_id == str(tenant_id)))
        if approval is None:
            return None
        await self._verify_access(UUID(str(approval.workspace_id)), tenant_id, user_id, is_superuser)
        if approval.status != "pending":
            raise ValueError("该审批已经处理，不能重复操作")
        approval.status, approval.reviewer_id, approval.comment, approval.reviewed_at = status, str(user_id), comment, _utcnow()
        run = await self.session.get(AgentRun, str(approval.agent_run_id))
        step = await self.session.get(AgentRunStep, str(approval.step_id)) if approval.step_id else None
        definition = await self.session.get(AgentDefinition, str(run.definition_id)) if run else None
        if run:
            is_tool_approval = self._is_tool_approval(definition, step)
            self._apply_approval_state(run, step, status, is_tool_approval)
            await self._update_research_review(run, status)
            if status == "approved" and is_tool_approval and step is not None and definition is not None:
                tool_key = str(self._workflow_step(definition.workflow or [], step.step_key).get("tool") or "")
                tool = self.tools.get(tool_key)
                if tool is not None:
                    try:
                        await self._execute_registered_tool(run, step, tool, step.input_json or {}, approval)
                    except Exception as exc:
                        # 审批已经是明确的业务动作；工具本身失败时保留审批结果，
                        # 将运行置为失败，供前端展示原因和提供“重试”，而不是
                        # 因异常回滚成待审批状态。
                        run.status = "failed"
                        run.error_message = str(exc)[:2000]
                        run.current_step = step.step_key
                        await self.session.flush()
        await self.session.flush()
        return await self._approval_dict(approval)

    def _is_tool_approval(self, definition: AgentDefinition | None, step: AgentRunStep | None) -> bool:
        if definition is None or step is None:
            return False
        tool_key = str(self._workflow_step(definition.workflow or [], step.step_key).get("tool") or "")
        return self.tools.get(tool_key) is not None

    @staticmethod
    def _apply_approval_state(run: AgentRun, step: AgentRunStep | None, status: str, is_tool_approval: bool) -> None:
        if is_tool_approval and step is not None:
            run.status, run.current_step, run.progress = ("queued", step.step_key, run.progress) if status == "approved" else ("rejected", step.step_key, 90)
            if status == "approved":
                step.status = "pending"
            return
        run.status, run.current_step, run.progress = ("completed", "human_review", 100) if status == "approved" else ("rejected", "human_review", 90)

    async def _update_research_review(self, run: AgentRun, status: str) -> None:
        if not run.research_run_id:
            return
        report = await self.session.scalar(select(ResearchReport).where(ResearchReport.run_id == str(run.research_run_id)))
        if report and report.review_status == "draft":
            report.review_status = status
