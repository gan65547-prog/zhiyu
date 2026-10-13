<template>
  <section class="research-home">
    <header class="page-header">
      <div>
        <p class="eyebrow">
          AI 工作台 / 研究洞察
        </p><h1>行业知识研究</h1><p class="subtitle">
          选择内部素材或用户指定 URL，形成可追溯的研究运行和证据报告。
        </p>
      </div><el-button
        type="primary"
        :disabled="!workspaceId"
        @click="dialogVisible = true"
      >
        <el-icon><Plus /></el-icon> 新建研究项目
      </el-button>
    </header>
    <el-alert
      type="info"
      :closable="false"
      show-icon
    >
      当前首版先生成证据包，不配置分析模型时不会自动编造行业结论。
    </el-alert>
    <el-alert v-if="quotaNotice" type="warning" :closable="true" show-icon class="quota-alert" @close="quotaNotice = ''">
      <template #default><span>{{ quotaNotice }}</span></template>
    </el-alert>
    <div v-if="quotaStatus" class="quota-summary" :class="{ 'quota-summary--blocked': !quotaStatus.is_ok }">
      <div><span class="section-kicker">MONTHLY QUOTA</span><strong>研究来源配额</strong><small>运行研究前先检查本月可用额度</small></div>
      <div class="quota-summary__value"><b>{{ quotaStatus.current }} / {{ quotaStatus.limit }}</b><span>剩余 {{ quotaStatus.remaining }} · {{ Math.round(quotaStatus.percentage) }}%</span></div>
    </div>
    <div class="project-grid">
      <el-card
        v-for="project in projects"
        :key="project.id"
        shadow="never"
        class="project-card"
      >
        <div class="project-head">
          <div><h3>{{ project.name }}</h3><span>{{ project.sample_count }} 个研究样本 · {{ project.questions.length }} 个研究问题</span></div><el-tag size="small">
            {{ project.status === 'active' ? '可运行' : project.status }}
          </el-tag>
        </div><p>{{ project.description || '暂无描述' }}</p><div class="run-list">
          <div
            v-for="run in runsByProject[project.id] || []"
            :key="run.id"
            class="run-row"
          >
            <span>{{ stageLabel(run) }}</span><el-progress
              :percentage="run.progress"
              :status="run.status === 'failed' ? 'exception' : run.status === 'cancelled' ? 'warning' : run.status === 'completed' ? 'success' : undefined"
              :stroke-width="7"
            /><el-button
              v-if="run.report_id"
              text
              type="primary"
              @click="openReport(run)"
            >
              报告
            </el-button><el-button
              v-if="!['completed', 'failed', 'cancelled'].includes(run.status)"
              text
              type="danger"
              @click="cancelRun(run)"
            >
              取消
            </el-button>
            <el-button
              v-if="['failed', 'cancelled'].includes(run.status)"
              text
              type="primary"
              :disabled="Boolean(quotaStatus && !quotaStatus.is_ok)"
              @click="retryRun(run)"
            >
              重试
            </el-button>
          </div><span
            v-if="!(runsByProject[project.id] || []).length"
            class="empty-run"
          >还没有运行记录</span>
        </div><el-button
          type="primary"
          plain
          :loading="runningId === project.id"
          :disabled="Boolean(quotaStatus && !quotaStatus.is_ok)"
          @click="startRun(project)"
        >
          {{ quotaStatus && !quotaStatus.is_ok ? '额度不足' : '运行研究' }}
        </el-button>
      </el-card>
    </div>
    <el-empty
      v-if="!loading && !projects.length"
      description="还没有研究项目"
    />
    <el-dialog
      v-model="dialogVisible"
      title="新建研究项目"
      width="620px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item
          label="项目名称"
          required
        >
          <el-input
            v-model="form.name"
            placeholder="例如：2026 年智能制造行业趋势"
          />
        </el-form-item><el-form-item
          label="研究问题"
          required
        >
          <el-input
            v-model="form.question"
            type="textarea"
            :rows="3"
            placeholder="例如：行业客户当前最关注哪些能力？"
          />
        </el-form-item><el-form-item label="用户指定 URL（可选）">
          <el-input
            v-model="form.source_uri"
            placeholder="https://example.com/report"
          />
        </el-form-item><el-form-item label="项目描述">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
          />
        </el-form-item>
        <el-form-item label="绑定内部知识库（可选）">
          <el-select
            v-model="form.dataset_id"
            clearable
            filterable
            placeholder="选择后将优先使用知识库内的证据"
            style="width: 100%"
          >
            <el-option
              v-for="dataset in datasets"
              :key="dataset.id"
              :label="dataset.name"
              :value="dataset.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="启用受控外部搜索">
          <el-switch v-model="form.external_search" />
        </el-form-item>
        <el-form-item
          v-if="form.external_search"
          label="外部搜索问题"
        >
          <el-input
            v-model="form.search_query"
            placeholder="例如：2026 年智能制造行业趋势"
          />
        </el-form-item>
      </el-form><template #footer>
        <el-button @click="dialogVisible = false">
          取消
        </el-button><el-button
          type="primary"
          :loading="submitting"
          @click="createProject"
        >
          创建项目
        </el-button>
      </template>
    </el-dialog>
    <el-dialog
      v-model="reportVisible"
      title="研究证据报告"
      width="760px"
      destroy-on-close
    >
      <el-alert
        v-if="report?.content_json?.evidence_only === true"
        type="info"
        :closable="false"
        show-icon
      >
        当前报告为证据包，结论仍需人工审核；引用内容来自本次研究运行的来源。
      </el-alert>
      <el-alert
        v-if="sourceCollectionNotice"
        type="warning"
        :closable="false"
        show-icon
      >
        {{ sourceCollectionNotice }}
      </el-alert>
      <el-input
        v-if="editingReport"
        v-model="reportContent"
        type="textarea"
        :rows="18"
        class="report-editor"
      />
      <pre v-else class="report-content">{{ report?.content_markdown || '报告生成中' }}</pre>
      <div
        v-if="findings.length || evidence.length"
        class="evidence-workspace"
      >
        <h3>研究发现</h3>
        <el-empty
          v-if="!findings.length"
          description="暂无结构化发现"
          :image-size="55"
        />
        <div
          v-for="finding in findings"
          :key="finding.id"
          class="finding-card"
        >
          <strong>{{ finding.claim }}</strong>
          <span>置信度 {{ Math.round(finding.confidence * 100) }}% · {{ finding.evidence_ids.length }} 条证据 · {{ finding.review_status === 'pending' ? '待审核' : finding.review_status }}</span>
        </div>
        <h3>证据摘录</h3>
        <div
          v-for="item in evidence"
          :key="item.id"
          class="evidence-row"
        >
          <strong>{{ item.source_title || item.source_uri || '未命名来源' }}</strong>
          <p>{{ item.quote }}</p>
          <small>{{ item.locator || '未提供位置' }}</small>
        </div>
      </div>
      <el-form
        v-if="report?.review_status === 'approved' && !report.published_dataset_id"
        label-position="top"
        class="publish-form"
      >
        <el-form-item label="发布到知识库">
          <el-select
            v-model="publishDatasetId"
            placeholder="选择当前工作空间的数据集"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="dataset in datasets"
              :key="dataset.id"
              :label="dataset.name"
              :value="dataset.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reportVisible = false">
          关闭
        </el-button>
        <el-button
          v-if="report && !report.published_dataset_id && !report.published_knowledge_item_id"
          plain
          @click="editingReport = !editingReport"
        >
          {{ editingReport ? '取消编辑' : '编辑报告' }}
        </el-button>
        <el-button
          v-if="editingReport"
          type="warning"
          :loading="savingReport"
          @click="saveReport"
        >
          保存并重新审核
        </el-button>
        <el-button
          v-if="report"
          type="danger"
          plain
          @click="reviewReport('rejected')"
        >
          驳回
        </el-button>
        <el-button
          v-if="report"
          type="primary"
          @click="reviewReport('approved')"
        >
          审核通过
        </el-button>
        <el-button
          v-if="report?.review_status === 'approved' && !report.published_dataset_id"
          type="success"
          :disabled="!publishDatasetId"
          @click="publishReport"
        >
          发布到知识库
        </el-button>
        <el-button
          v-if="report?.review_status === 'approved' && !report.published_knowledge_item_id"
          type="success"
          plain
          @click="publishToKnowledge"
        >
          沉淀为知识卡片
        </el-button>
        <el-button
          v-if="report?.review_status === 'approved'"
          type="warning"
          plain
          @click="createContentDraft"
        >
          生成内容草稿
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { Plus } from '@element-plus/icons-vue'
import { researchApi } from '@/api/research'
import { contentApi } from '@/api/content'
import { getDatasets } from '@/api/dataset'
import type { ResearchEvidence, ResearchFinding, ResearchProject, ResearchReport, ResearchRun } from '@/types/research'
import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()
const router = useRouter()
const route = useRoute()
const workspaceId = computed(() => workspaceStore.currentWorkspaceId)
const projects = ref<ResearchProject[]>([])
const runsByProject = ref<Record<string, ResearchRun[]>>({})
const loading = ref(false)
const submitting = ref(false)
const runningId = ref<string | null>(null)
const dialogVisible = ref(false)
const quotaNotice = ref('')
const quotaStatus = ref<{ current: number; limit: number; remaining: number; percentage: number; is_ok: boolean } | null>(null)
const reportVisible = ref(false)
const report = ref<ResearchReport | null>(null)
const editingReport = ref(false)
const savingReport = ref(false)
const reportContent = ref('')
const evidence = ref<ResearchEvidence[]>([])
const findings = ref<ResearchFinding[]>([])
const datasets = ref<Array<{ id: string; name: string }>>([])
const publishDatasetId = ref('')
const form = reactive({ name: '', question: '', source_uri: '', dataset_id: '', description: '', external_search: false, search_query: '' })
let refreshTimer: number | undefined
const targetRunHandled = ref(false)
function showActionError(error: unknown, fallback: string) {
  const message = error instanceof Error && error.message ? error.message : fallback
  ElMessage.error(message)
}
const sourceCollectionNotice = computed(() => {
  const status = report.value?.content_json?.source_collection
  if (!status || typeof status !== 'object') return ''
  const data = status as { enabled?: boolean; attempted?: number; failed?: number; fallback?: string }
  if (!data.enabled || !data.failed) return ''
  return `外部搜索失败 ${data.failed}/${data.attempted || data.failed} 次，本报告已回退到内部来源；请在审核时关注来源覆盖范围。`
})

async function loadProjects() {
  if (!workspaceId.value) return
  loading.value = true
  try {
    try {
      projects.value = (await researchApi.listProjects(workspaceId.value)).items || []
    } catch (error) {
      projects.value = []
      runsByProject.value = {}
      showActionError(error, '研究项目加载失败')
      return
    }
    const entries = await Promise.all(projects.value.map(async project => {
      try {
        return [project.id, (await researchApi.listRuns(project.id)).items || []] as const
      } catch {
        return [project.id, []] as const
      }
    }))
    runsByProject.value = Object.fromEntries(entries)
    if (!targetRunHandled.value && route.query.run_id) {
      const target = Object.values(runsByProject.value).flat().find(run => run.id === String(route.query.run_id))
      if (target) {
        targetRunHandled.value = true
        if (target.report_id) await openReport(target)
        else ElMessage.info('已定位到研究运行，报告尚未生成')
      }
    }
  } finally { loading.value = false }
}
async function createProject() {
  if (!workspaceId.value || !form.name.trim() || !form.question.trim()) return ElMessage.warning('请填写项目名称和研究问题')
  submitting.value = true
  try {
    const metadata = form.external_search && form.search_query.trim() ? { external_search: { enabled: true, queries: [form.search_query.trim()] } } : {}
    const samples = form.dataset_id
      ? [{ dataset_id: form.dataset_id }]
      : (form.source_uri.trim() ? [{ source_uri: form.source_uri.trim() }] : [])
    try {
      await researchApi.createProject({ workspace_id: workspaceId.value, name: form.name.trim(), description: form.description.trim() || undefined, questions: [{ question: form.question.trim(), sort_order: 0 }], samples, metadata })
    } catch (error) {
      quotaNotice.value = quotaMessage(error)
      throw error
    }
    Object.assign(form, { name: '', question: '', source_uri: '', dataset_id: '', description: '', external_search: false, search_query: '' }); dialogVisible.value = false; ElMessage.success('研究项目已创建'); await loadProjects()
  } catch (error) { if (!quotaNotice.value) showActionError(error, '研究项目创建失败') } finally { submitting.value = false }
}
async function startRun(project: ResearchProject) {
  if (quotaStatus.value && !quotaStatus.value.is_ok) {
    quotaNotice.value = `本月研究来源配额已用完（${quotaStatus.value.current}/${quotaStatus.value.limit}），请联系部署管理员调整资源限制`
    return
  }
  runningId.value = project.id
  try {
    await researchApi.createRun(project.id)
    ElMessage.success('研究运行已提交')
    await Promise.allSettled([loadProjects(), loadQuota()])
  } catch (error) {
    quotaNotice.value = quotaMessage(error)
    if (!quotaNotice.value) showActionError(error, '研究运行提交失败')
    await loadQuota()
  } finally { runningId.value = null }
}
async function cancelRun(run: ResearchRun) { try { await researchApi.cancelRun(run.id); ElMessage.success('研究运行已取消'); await loadProjects() } catch (error) { showActionError(error, '取消研究运行失败') } }
async function retryRun(run: ResearchRun) { try { await researchApi.retryRun(run.id); ElMessage.success('研究运行已重新排队'); await loadProjects() } catch (error) { showActionError(error, '研究运行重试失败') } }
async function openReport(run: ResearchRun) {
  try {
    report.value = await researchApi.getReport(run.id)
    reportContent.value = report.value.content_markdown
    editingReport.value = false;
    [evidence.value, findings.value] = await Promise.all([
      researchApi.listRunEvidence(run.id),
      researchApi.listRunFindings(run.id)
    ])
    publishDatasetId.value = report.value.published_dataset_id || ''
    if (report.value.review_status === 'approved' && !report.value.published_dataset_id) await loadDatasets()
    reportVisible.value = true
  } catch (error) { showActionError(error, '报告加载失败') }
}
async function saveReport() {
  if (!report.value || !reportContent.value.trim()) return ElMessage.warning('报告内容不能为空')
  savingReport.value = true
  try {
    report.value = await researchApi.updateReport(report.value.id, reportContent.value)
    editingReport.value = false
    ElMessage.success('报告已更新，等待重新审核')
  } catch (error) { showActionError(error, '报告保存失败') } finally { savingReport.value = false }
}
async function reviewReport(reviewStatus: 'approved' | 'rejected') {
  if (!report.value) return
  try {
    report.value = await researchApi.reviewReport(report.value.id, reviewStatus)
    if (reviewStatus === 'approved') await loadDatasets()
    ElMessage.success(reviewStatus === 'approved' ? '报告已审核通过' : '报告已驳回')
  } catch (error) { showActionError(error, '报告审核失败') }
}
async function loadDatasets() {
  if (!workspaceId.value) return
  const result = await getDatasets({ workspace_id: workspaceId.value, page: 1, page_size: 100 })
  const items = Array.isArray(result) ? result : result?.items || result?.data?.items || []
  datasets.value = items.map((item: { id: string; name: string }) => ({ id: item.id, name: item.name }))
}
async function publishReport() {
  if (!report.value || !publishDatasetId.value) return
  try { report.value = await researchApi.publishReport(report.value.id, publishDatasetId.value); ElMessage.success('报告已发布，正在进入知识库处理队列') } catch (error) { showActionError(error, '报告发布失败') }
}
async function publishToKnowledge() {
  if (!report.value) return
  try { report.value = await researchApi.publishToKnowledge(report.value.id); ElMessage.success('报告已沉淀为待审核知识卡片') } catch (error) { showActionError(error, '报告沉淀失败') }
}
async function createContentDraft() {
  if (!report.value) return
  try { await contentApi.createDraftFromResearch(report.value.id); ElMessage.success('内容草稿已生成，等待内容审核') } catch (error) { showActionError(error, '内容草稿生成失败') }
}
const runStageLabels: Record<string, string> = {
  pending: '排队中',
  searching: '搜索来源中',
  collecting_sources: '收集来源',
  building_evidence: '整理证据',
  synthesizing_findings: '综合发现',
  generate_report: '生成报告',
  human_review: '等待人工审核',
  completed: '已完成',
  cancelled: '已取消',
}
function stageLabel(run: ResearchRun) {
  if (run.status === 'failed') return `失败：${run.error_message || '处理失败'}`
  if (run.status === 'cancelled') return '已取消'
  if (run.status === 'completed') return '已完成'
  return runStageLabels[run.current_stage || run.status] || '排队中'
}
function quotaMessage(error: unknown) { const body = (error as { response?: { data?: { detail?: unknown; error?: string; message?: string; upgrade_hint?: string } } }).response?.data; const detail = body?.detail && typeof body.detail === 'object' ? body.detail as { error?: string; message?: string; upgrade_hint?: string } : body; return detail?.error === 'QUOTA_EXCEEDED' ? detail.message || '当前研究来源资源上限已达到，请联系部署管理员' : '' }
async function loadQuota() {
  quotaStatus.value = null
}
onMounted(async () => {
  await workspaceStore.fetchCurrentWorkspace()
  await Promise.allSettled([loadProjects(), loadDatasets(), loadQuota()])
  refreshTimer = window.setInterval(() => { if (projects.value.length) void loadProjects() }, 15000)
})
onUnmounted(() => { if (refreshTimer) window.clearInterval(refreshTimer) })
</script>

<style scoped lang="scss">
.research-home { max-width: 1440px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.eyebrow { margin: 0 0 8px; color: var(--el-color-primary); font-size: 12px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; }
h1 { margin: 0; color: var(--el-text-color-primary); font-family: Georgia, 'Times New Roman', serif; font-size: clamp(30px, 4vw, 46px); letter-spacing: -.04em; }
.subtitle { max-width: 680px; margin: 10px 0 0; color: var(--el-text-color-secondary); line-height: 1.7; }
.project-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; margin-top: 22px; }
.quota-summary { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 16px; padding: 14px 18px; border: 1px solid rgba(112,74,198,.14); border-radius: 15px; background: linear-gradient(120deg, #fbf9ff, #f2eaff); }.quota-summary--blocked { border-color: rgba(194,119,28,.3); background: linear-gradient(120deg, #fffaf0, #fff4dd); }.quota-summary > div:first-child { display: flex; flex-direction: column; gap: 4px; }.quota-summary strong { color: var(--el-text-color-primary); }.quota-summary small, .quota-summary__value span { color: var(--el-text-color-secondary); font-size: 12px; }.quota-summary__value { display: flex; flex-direction: column; gap: 4px; text-align: right; }.quota-summary__value b { font-size: 20px; color: var(--el-color-primary); }
.project-card { border: 1px solid rgba(112, 74, 198, .14); border-radius: 18px; background: linear-gradient(145deg, rgba(255,255,255,.96), rgba(249,247,255,.9)); box-shadow: 0 12px 30px rgba(79, 51, 133, .06); }
.project-card :deep(.el-card__body) { padding: 22px; }
.project-head { display: flex; justify-content: space-between; gap: 12px; }
.project-head h3 { margin: 0 0 8px; font-size: 19px; letter-spacing: -.02em; }
.project-head span, .project-card p { color: var(--el-text-color-secondary); font-size: 13px; }
.project-card p { min-height: 40px; line-height: 1.7; }
.run-list { margin: 18px 0; padding: 12px 14px; background: rgba(116, 79, 205, .055); border: 1px solid rgba(116, 79, 205, .1); border-radius: 12px; }
.run-row { display: grid; grid-template-columns: 120px 1fr auto; align-items: center; gap: 10px; margin: 9px 0; font-size: 12px; }
.empty-run { color: var(--el-text-color-secondary); font-size: 12px; }
.el-input, .el-textarea { width: 100%; }
.report-content { border: 1px solid rgba(112, 74, 198, .1); }
.report-content { max-height: 55vh; overflow: auto; margin: 16px 0 0; padding: 16px; white-space: pre-wrap; word-break: break-word; background: var(--el-fill-color-lighter); border-radius: 10px; font: inherit; line-height: 1.7; }
.publish-form { margin-top: 16px; }
.evidence-workspace { margin-top: 20px; }.evidence-workspace h3 { margin: 18px 0 10px; }.finding-card, .evidence-row { padding: 12px; margin-bottom: 8px; background: var(--el-fill-color-lighter); border-radius: 10px; }.finding-card span, .evidence-row small { display: block; margin-top: 6px; color: var(--el-text-color-secondary); font-size: 12px; }.evidence-row p { margin: 8px 0; line-height: 1.6; white-space: pre-wrap; }
@media (max-width: 760px) { .page-header { display: block; }.page-header .el-button { margin-top: 16px; }.project-grid { grid-template-columns: 1fr; }.quota-summary { align-items: flex-start; flex-direction: column; }.quota-summary__value { text-align: left; } }
.report-content { max-height: 55vh; overflow: auto; margin: 16px 0 0; padding: 16px; white-space: pre-wrap; word-break: break-word; background: var(--el-fill-color-lighter); border-radius: 8px; font: inherit; line-height: 1.6; }
.publish-form { margin-top: 16px; }
.evidence-workspace { margin-top: 20px; }.evidence-workspace h3 { margin: 18px 0 10px; }.finding-card, .evidence-row { padding: 12px; margin-bottom: 8px; background: var(--el-fill-color-lighter); border-radius: 8px; }.finding-card span, .evidence-row small { display: block; margin-top: 6px; color: var(--el-text-color-secondary); font-size: 12px; }.evidence-row p { margin: 8px 0; line-height: 1.6; white-space: pre-wrap; }
</style>
