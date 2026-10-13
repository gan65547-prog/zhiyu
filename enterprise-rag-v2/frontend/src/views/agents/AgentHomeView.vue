<template>
  <section class="agent-home">
    <header class="page-header">
      <div>
        <p class="eyebrow">
          AI 工作台 / Agent 中心
        </p>
        <h1>Agent 运行中心</h1>
        <p class="subtitle">
          查看研究工作流的步骤、状态和中间结果。
        </p>
      </div>
      <div class="header-actions"><el-button plain @click="definitionDialog = true">新建工具 Agent</el-button><el-button type="primary" plain @click="toolRunDialog = true">运行白名单工具</el-button></div>
    </header>
    <el-alert
      type="info"
      :closable="false"
      show-icon
    >
      当前只展示显式、可审计的研究分析工作流；不会执行未登记的任意工具步骤。
    </el-alert>
    <div class="agent-summary">
      <article v-for="metric in summaryMetrics" :key="metric.label" class="summary-card" :class="metric.tone">
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
        <small>{{ metric.detail }}</small>
      </article>
    </div>
    <el-card shadow="never" class="tools-card">
      <template #header><div class="run-head"><strong>白名单工具</strong><span>只读工具，外部访问统一经过安全边界</span></div></template>
      <el-space wrap>
        <el-tag v-for="tool in tools" :key="tool.key" :type="tool.requires_approval ? 'warning' : 'info'">
          {{ tool.label }}{{ tool.requires_approval ? ' · 需审批' : '' }}
        </el-tag>
      </el-space>
    </el-card>
    <div class="run-grid">
      <el-card
        v-for="run in runs"
        :key="run.id"
        shadow="never"
        class="run-card"
        @click="openRun(run)"
      >
        <div class="run-head">
          <div>
            <h3>研究 Agent</h3>
            <span>{{ run.id }}</span>
          </div>
          <el-tag :type="statusType(run.status)">
            {{ statusLabel(run.status) }}
          </el-tag>
        </div>
        <el-progress
          :percentage="run.progress"
          :status="run.status === 'failed' ? 'exception' : undefined"
        />
        <el-steps
          :active="activeStep(run)"
          finish-status="success"
          align-center
        >
          <el-step
            v-for="step in run.steps"
            :key="step.id"
            :title="stepLabel(step.step_key)"
            :status="step.status === 'failed' ? 'error' : undefined"
          />
        </el-steps>
        <div class="run-footer">
          <span>{{ run.current_step || '排队中' }}</span>
          <el-button
            v-if="!['completed', 'failed', 'cancelled'].includes(run.status)"
            text
            type="danger"
            @click="cancelRun(run)"
          >
            取消
          </el-button>
          <el-button
            v-if="['failed', 'cancelled', 'rejected'].includes(run.status)"
            text
            type="primary"
            @click="retryRun(run)"
          >
            重试
          </el-button>
        </div>
      </el-card>
    </div>
    <el-dialog
      v-model="runDialog"
      title="Agent 执行事件"
      width="720px"
      destroy-on-close
    >
      <el-timeline v-if="events.length">
        <el-timeline-item
          v-for="event in events"
          :key="`${event.event_type}-${event.id}`"
          :timestamp="event.created_at"
        >
          <strong>{{ event.title || event.step_key || event.event_type }}</strong>
          <el-tag size="small" class="event-status">{{ event.status }}</el-tag>
          <pre class="event-content">{{ JSON.stringify(event.content, null, 2) }}</pre>
        </el-timeline-item>
      </el-timeline>
      <el-empty
        v-else
        description="暂无中间产物"
      />
    </el-dialog>
    <el-empty
      v-if="!loading && !runs.length"
      description="还没有 Agent 运行记录"
    />
    <el-card shadow="never" class="schedule-card">
      <template #header>
        <div class="run-head"><strong>定时任务</strong><span>由 Celery Beat 每分钟投递到研究队列</span><el-button type="primary" size="small" @click="scheduleDialog = true">新建调度</el-button></div>
      </template>
      <el-table v-if="schedules.length" :data="schedules" size="small">
        <el-table-column prop="name" label="任务" min-width="160" />
        <el-table-column prop="schedule_expression" label="表达式" width="150" />
        <el-table-column prop="next_run_at" label="下次运行" min-width="180" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '已启用' : '已停用' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }"><el-button text type="primary" @click="toggleSchedule(row)">{{ row.enabled ? '停用' : '启用' }}</el-button></template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="还没有定时任务，可通过 Agent 调度 API 创建" />
    </el-card>
    <el-dialog v-model="scheduleDialog" title="新建 Agent 调度" width="520px">
      <el-form label-width="110px">
        <el-form-item label="任务名称"><el-input v-model="scheduleForm.name" /></el-form-item>
        <el-form-item label="Agent 定义"><el-select v-model="scheduleForm.definition_id" placeholder="选择定义"><el-option v-for="item in definitions" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="研究项目"><el-select v-model="scheduleForm.project_id" placeholder="选择项目"><el-option v-for="item in projects" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="调度表达式"><el-input v-model="scheduleForm.schedule_expression" placeholder="*/30 * * * *" /></el-form-item>
        <el-form-item label="首次运行"><el-date-picker v-model="scheduleForm.next_run_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="scheduleDialog = false">取消</el-button><el-button type="primary" :loading="savingSchedule" @click="createSchedule">创建</el-button></template>
    </el-dialog>
    <el-dialog v-model="toolRunDialog" title="运行白名单工具" width="560px">
      <el-alert type="warning" :closable="false" show-icon>工具只能来自已登记工作流；需要外部访问的工具会先进入人工审批。</el-alert>
      <el-form label-width="100px" class="tool-run-form">
        <el-form-item label="Agent 定义"><el-select v-model="toolRunForm.definition_id" placeholder="选择含工具步骤的定义" style="width: 100%"><el-option v-for="item in toolDefinitions" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="工具步骤"><el-select v-model="toolRunForm.step_key" placeholder="选择工具步骤" style="width: 100%"><el-option v-for="step in selectedToolSteps" :key="step.key" :label="`${step.key} · ${step.tool}`" :value="step.key" /></el-select></el-form-item>
        <el-form-item label="工具输入"><el-input v-model="toolRunForm.input" type="textarea" :rows="5" placeholder='例如 {"text":"AI 工作台"}' /></el-form-item>
      </el-form>
      <template #footer><el-button @click="toolRunDialog = false">取消</el-button><el-button type="primary" :loading="runningTool" @click="runTool">创建并运行</el-button></template>
    </el-dialog>
    <el-dialog v-model="definitionDialog" title="新建工具 Agent" width="560px">
      <el-alert type="info" :closable="false" show-icon>只能绑定已登记工具；外部访问工具运行前仍需人工审批。</el-alert>
      <el-form label-width="100px" class="tool-run-form">
        <el-form-item label="名称"><el-input v-model="definitionForm.name" placeholder="例如：网页术语采集" /></el-form-item>
        <el-form-item label="Agent 类型"><el-select v-model="definitionForm.agent_type" style="width: 100%"><el-option label="研究分析" value="research_analysis" /><el-option label="素材整理" value="asset_organize" /></el-select></el-form-item>
        <el-form-item label="工具步骤"><el-select v-model="definitionForm.tool" style="width: 100%"><el-option v-for="tool in tools" :key="tool.key" :label="tool.label" :value="tool.key" /></el-select></el-form-item>
        <el-form-item label="步骤名称"><el-input v-model="definitionForm.step_key" placeholder="例如：collect_terms" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="definitionForm.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="definitionDialog = false">取消</el-button><el-button type="primary" :loading="savingDefinition" @click="createToolDefinition">创建</el-button></template>
    </el-dialog>
    <el-card shadow="never" class="approval-card">
      <template #header><div class="run-head"><strong>待审批产物</strong><el-tag type="warning">{{ approvals.length }}</el-tag></div></template>
      <el-table v-if="approvals.length" :data="approvals" size="small">
        <el-table-column prop="agent_run_id" label="Agent 运行" min-width="220" />
        <el-table-column prop="step_key" label="节点" width="150" />
        <el-table-column prop="created_at" label="提交时间" min-width="180" />
        <el-table-column label="操作" width="170">
          <template #default="{ row }">
            <el-button text type="success" @click="reviewApproval(row, 'approved')">通过</el-button>
            <el-button text type="danger" @click="reviewApproval(row, 'rejected')">驳回</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="暂无待审批 Agent 产物" />
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { agentApi } from '@/api/agent'
import { researchApi } from '@/api/research'
import type { AgentApproval, AgentDefinition, AgentEvent, AgentRun, AgentRunStep, AgentSchedule, AgentTool } from '@/types/agent'
import type { ResearchProject } from '@/types/research'
import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()
const route = useRoute()
const workspaceId = computed(() => workspaceStore.currentWorkspaceId)
const runs = ref<AgentRun[]>([])
const schedules = ref<AgentSchedule[]>([])
const approvals = ref<AgentApproval[]>([])
const tools = ref<AgentTool[]>([])
const events = ref<AgentEvent[]>([])
const runDialog = ref(false)
const definitions = ref<AgentDefinition[]>([])
const projects = ref<ResearchProject[]>([])
const scheduleDialog = ref(false)
const toolRunDialog = ref(false)
const definitionDialog = ref(false)
const runningTool = ref(false)
const savingDefinition = ref(false)
const savingSchedule = ref(false)
const scheduleForm = ref({ name: '', definition_id: '', project_id: '', schedule_expression: '*/30 * * * *', next_run_at: '' })
const toolRunForm = ref({ definition_id: '', step_key: '', input: '{}' })
const definitionForm = ref({ name: '', agent_type: 'research_analysis', tool: '', step_key: 'tool_step', description: '' })
const loading = ref(false)
let refreshTimer: number | undefined
const targetRunId = computed(() => String(route.query.run_id || ''))
const targetRunHandled = ref(false)
const summaryMetrics = computed(() => [
  { label: '运行总数', value: runs.value.length, detail: '当前工作空间', tone: '' },
  { label: '执行中', value: runs.value.filter(run => ['queued', 'running'].includes(run.status)).length, detail: '正在推进的工作流', tone: 'warm' },
  { label: '待审批', value: approvals.value.length, detail: '需要人工确认', tone: 'accent' },
  { label: '已启用调度', value: schedules.value.filter(item => item.enabled).length, detail: '由后台定时投递', tone: 'green' },
])

async function loadRuns() {
  if (!workspaceId.value) return
  loading.value = true
  try { runs.value = (await agentApi.listRuns(workspaceId.value)).items || [] } catch { runs.value = [] } finally { loading.value = false }
}
async function loadSchedules() { if (workspaceId.value) { try { schedules.value = await agentApi.listSchedules(workspaceId.value) } catch { schedules.value = [] } } }
async function loadApprovals() { if (workspaceId.value) { try { approvals.value = await agentApi.listApprovals(workspaceId.value) } catch { approvals.value = [] } } }
async function loadScheduleOptions() {
  if (!workspaceId.value) return
  const [definitionResult, projectResult] = await Promise.allSettled([agentApi.listDefinitions(workspaceId.value), researchApi.listProjects(workspaceId.value)])
  definitions.value = definitionResult.status === 'fulfilled' ? definitionResult.value : []
  projects.value = projectResult.status === 'fulfilled' ? projectResult.value.items || [] : []
}
const toolDefinitions = computed(() => definitions.value.filter(item => Array.isArray(item.workflow) && item.workflow.some(step => Boolean(step.tool))))
const selectedToolSteps = computed(() => {
  const workflow = definitions.value.find(item => item.id === toolRunForm.value.definition_id)?.workflow
  return Array.isArray(workflow) ? workflow.filter(step => Boolean(step.tool)) : []
})
async function openRun(run: AgentRun) {
  events.value = await agentApi.listEvents(run.id)
  runDialog.value = true
}
async function createSchedule() {
  if (!workspaceId.value || !scheduleForm.value.definition_id || !scheduleForm.value.project_id || !scheduleForm.value.next_run_at) { ElMessage.warning('请完整填写调度信息'); return }
  savingSchedule.value = true
  try { await agentApi.createSchedule({ workspace_id: workspaceId.value, ...scheduleForm.value, timezone: 'Asia/Shanghai' }); scheduleDialog.value = false; ElMessage.success('调度已创建'); await loadSchedules() } finally { savingSchedule.value = false }
}
async function runTool() {
  if (!workspaceId.value || !toolRunForm.value.definition_id || !toolRunForm.value.step_key) { ElMessage.warning('请选择含工具步骤的 Agent 定义和步骤'); return }
  let input: Record<string, unknown>
  try { input = JSON.parse(toolRunForm.value.input || '{}') } catch { ElMessage.error('工具输入必须是有效 JSON'); return }
  runningTool.value = true
  try {
    const run = await agentApi.createRun({ workspace_id: workspaceId.value, definition_id: toolRunForm.value.definition_id })
    const result = await agentApi.executeToolStep(run.id, toolRunForm.value.step_key, input)
    toolRunDialog.value = false
    if (result.status === 'failed') ElMessage.error('工具执行失败，可在运行卡片中重试')
    else ElMessage.success(result.status === 'waiting_approval' ? '工具已提交，等待人工审批' : '工具执行完成')
    toolRunForm.value = { definition_id: '', step_key: '', input: '{}' }
    await Promise.all([loadRuns(), loadApprovals()])
  } catch (error: any) {
    const message = error?.response?.data?.detail || error?.message || '工具运行失败，请稍后重试'
    ElMessage.error(String(message))
  } finally { runningTool.value = false }
}
async function createToolDefinition() {
  if (!workspaceId.value || !definitionForm.value.name.trim() || !definitionForm.value.tool || !definitionForm.value.step_key.trim()) { ElMessage.warning('请填写名称、工具和步骤名称'); return }
  savingDefinition.value = true
  try {
    const definition = await agentApi.createDefinition({
      workspace_id: workspaceId.value,
      name: definitionForm.value.name.trim(),
      agent_type: definitionForm.value.agent_type,
      description: definitionForm.value.description.trim() || undefined,
      workflow: [{ key: definitionForm.value.step_key.trim(), label: definitionForm.value.name.trim(), tool: definitionForm.value.tool, input: {} }],
    })
    definitionDialog.value = false
    await loadScheduleOptions()
    toolRunForm.value.definition_id = definition.id
    toolRunForm.value.step_key = definitionForm.value.step_key.trim()
    definitionForm.value = { name: '', agent_type: 'research_analysis', tool: '', step_key: 'tool_step', description: '' }
    ElMessage.success('工具 Agent 定义已创建，可立即运行')
  } finally { savingDefinition.value = false }
}
async function toggleSchedule(schedule: AgentSchedule) { if (schedule.enabled) await agentApi.disableSchedule(schedule.id); else await agentApi.enableSchedule(schedule.id); await loadSchedules() }
async function reviewApproval(approval: AgentApproval, status: 'approved' | 'rejected') { await agentApi.reviewApproval(approval.id, status); ElMessage.success(status === 'approved' ? '审批已通过' : '审批已驳回'); await Promise.all([loadApprovals(), loadRuns()]) }
async function cancelRun(run: AgentRun) { await agentApi.cancelRun(run.id); ElMessage.success('Agent 运行已取消'); await loadRuns() }
async function retryRun(run: AgentRun) { await agentApi.retryRun(run.id); ElMessage.success('Agent 运行已重新排队'); await loadRuns() }
function activeStep(run: AgentRun) { return Math.max(0, run.steps.findIndex((step: AgentRunStep) => step.status === 'running')) }
function stepLabel(key: string) { return ({ collect_sources: '收集来源', build_evidence: '整理证据', synthesize_findings: '综合发现', generate_report: '生成报告', human_review: '人工审核' } as Record<string, string>)[key] || key }
function statusLabel(status: string) { return ({ queued: '排队中', running: '执行中', waiting_approval: '等待审核', completed: '已完成', failed: '失败', cancelled: '已取消' } as Record<string, string>)[status] || status }
function statusType(status: string) { return status === 'failed' ? 'danger' : status === 'completed' ? 'success' : status === 'waiting_approval' ? 'warning' : 'info' }
onMounted(async () => {
  await workspaceStore.fetchCurrentWorkspace()
  try { tools.value = await agentApi.listTools() } catch { tools.value = [] }
  await Promise.allSettled([loadRuns(), loadSchedules(), loadApprovals(), loadScheduleOptions()])
  if (targetRunId.value && !targetRunHandled.value) {
    const target = runs.value.find(run => run.id === targetRunId.value)
    if (target) { targetRunHandled.value = true; await openRun(target) }
  }
  refreshTimer = window.setInterval(() => { void loadRuns(); void loadSchedules(); void loadApprovals() }, 15000)
})
onUnmounted(() => { if (refreshTimer) window.clearInterval(refreshTimer) })
</script>

<style scoped lang="scss">
.agent-home { max-width: 1440px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.eyebrow { margin: 0 0 8px; color: var(--el-color-primary); font-size: 12px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; }
h1 { margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: clamp(30px, 4vw, 46px); letter-spacing: -.04em; }
.subtitle { margin: 10px 0 0; color: var(--el-text-color-secondary); line-height: 1.7; }
.agent-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 18px 0 20px; }
.summary-card { display: flex; min-height: 104px; flex-direction: column; justify-content: space-between; padding: 16px 18px; border: 1px solid rgba(112, 74, 198, .13); border-radius: 16px; background: linear-gradient(145deg, rgba(255,255,255,.98), rgba(249,247,255,.92)); box-shadow: 0 12px 30px rgba(79,51,133,.05); }
.summary-card span, .summary-card small { color: var(--el-text-color-secondary); font-size: 12px; }.summary-card strong { color: #2d2140; font-family: Georgia, 'Times New Roman', serif; font-size: 30px; letter-spacing: -.04em; }
.summary-card.warm { background: linear-gradient(145deg,#fffaf0,#fff); }.summary-card.warm strong { color: #b4771c; }.summary-card.accent { background: linear-gradient(145deg,#eee6ff,#fff); }.summary-card.accent strong { color: var(--el-color-primary); }.summary-card.green { background: linear-gradient(145deg,#f2fbf6,#fff); }.summary-card.green strong { color: #2f8a61; }
.tools-card, .schedule-card, .approval-card { margin-top: 20px; border: 1px solid rgba(112, 74, 198, .13); border-radius: 18px; box-shadow: 0 12px 30px rgba(79, 51, 133, .05); }
.tools-card :deep(.el-card__header), .schedule-card :deep(.el-card__header), .approval-card :deep(.el-card__header) { border-bottom-color: rgba(112, 74, 198, .1); }
.run-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 20px; }
.run-card { border: 1px solid rgba(112, 74, 198, .13); border-radius: 18px; cursor: pointer; transition: transform .2s ease, box-shadow .2s ease; }
.run-card:hover { transform: translateY(-2px); box-shadow: 0 14px 32px rgba(79, 51, 133, .1); }
.run-head, .run-footer { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.run-head h3 { margin: 0 0 6px; }.run-head span, .run-footer span { color: var(--el-text-color-secondary); font-size: 12px; }
.run-card .el-steps { margin: 22px 0 16px; }.event-status { margin-left: 8px; }
.event-content { margin-top: 8px; padding: 8px; overflow: auto; white-space: pre-wrap; background: var(--el-fill-color-lighter); border-radius: 8px; }
@media (max-width: 980px) { .agent-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .run-grid, .agent-summary { grid-template-columns: 1fr; } }
</style>
