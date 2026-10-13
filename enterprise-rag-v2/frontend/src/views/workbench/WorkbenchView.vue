<template>
  <section class="workbench-view">
    <header class="hero">
      <div>
        <p class="eyebrow">
          AI 工作台
        </p>
        <h1>把素材变成可用知识</h1>
        <p class="subtitle">
          从导入资料开始，持续沉淀、检索和复用团队知识。
        </p>
      </div>
      <div class="hero-actions">
        <el-button
          type="primary"
          :disabled="!workspaceId"
          @click="router.push('/assets')"
        >
          <el-icon><Upload /></el-icon>
          导入素材
        </el-button>
        <el-button
          :disabled="!workspaceId"
          @click="router.push('/chat')"
        >
          <el-icon><ChatDotRound /></el-icon>
          开始问答
        </el-button>
      </div>
    </header>

    <el-alert
      v-if="!workspaceId"
      type="warning"
      :closable="false"
      show-icon
    >
      请先选择或创建工作空间，再开始使用 AI 工作台。
    </el-alert>

    <div
      v-loading="loading"
      class="metric-grid"
    >
      <el-card
        v-for="metric in metrics"
        :key="metric.label"
        shadow="never"
        class="metric-card"
      >
        <div
          class="metric-icon"
          :class="metric.tone"
        >
          <el-icon><component :is="metric.icon" /></el-icon>
        </div>
        <div><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong></div>
      </el-card>
    </div>

    <el-card shadow="never" class="pipeline-panel">
      <template #header>
        <div class="panel-header">
          <div>
            <span class="section-kicker">WORKFLOW PIPELINE</span>
            <strong>知识生产流水线</strong>
          </div>
          <el-button text @click="router.push('/tasks')">查看待处理事项</el-button>
        </div>
      </template>
      <div class="pipeline-track">
        <button
          v-for="(stage, index) in pipelineStages"
          :key="stage.key"
          class="pipeline-stage"
          :class="{ 'is-active': stage.count > 0 }"
          @click="router.push(stage.route)"
        >
          <span class="stage-index">0{{ index + 1 }}</span>
          <span class="stage-copy"><strong>{{ stage.label }}</strong><small>{{ stage.description }}</small></span>
          <b>{{ stage.count }}</b>
          <span v-if="index < pipelineStages.length - 1" class="stage-connector" aria-hidden="true" />
        </button>
      </div>
    </el-card>

    <div class="content-grid">
      <el-card
        shadow="never"
        class="panel"
      >
        <template #header>
          <div class="panel-header">
            <span>待处理事项</span><el-button
              text
              @click="router.push('/tasks')"
            >
              查看全部
            </el-button>
          </div>
        </template>
        <div
          v-if="pendingTasks.length"
          class="task-list"
        >
          <div
            v-for="task in pendingTasks"
            :key="task.id"
            class="task-item"
            @click="router.push(task.route)"
          >
            <div class="task-main">
              <el-icon><Loading /></el-icon><span>{{ task.title }}</span>
            </div>
            <el-tag :type="task.type">
              {{ task.label }}
            </el-tag>
          </div>
        </div>
        <el-empty
          v-else
          description="暂无待处理事项"
          :image-size="72"
        />
      </el-card>

      <el-card
        shadow="never"
        class="panel"
      >
        <template #header>
          <div class="panel-header">
            <span>最近导入</span><el-button
              text
              @click="router.push('/assets')"
            >
              素材中心
            </el-button>
          </div>
        </template>
        <div
          v-if="recentActivities.length"
          class="recent-list"
        >
          <div
            v-for="activity in recentActivities"
            :key="activity.id"
            class="recent-item"
          >
            <div><strong>{{ activity.title }}</strong><span>{{ activity.kind }} · {{ formatDate(activity.created_at) }}</span></div>
            <el-tag size="small">
              {{ activity.label }}
            </el-tag>
          </div>
        </div>
        <el-empty
          v-else
          description="还没有素材"
          :image-size="72"
        />
      </el-card>
    </div>

    <el-card
      shadow="never"
      class="next-panel"
    >
      <template #header>
        <span>下一步</span>
      </template>
      <div class="next-actions">
        <button
          class="next-action"
          @click="router.push('/assets')"
        >
          <el-icon><Collection /></el-icon><span><strong>沉淀素材</strong><small>上传文件或导入网页</small></span><el-icon><ArrowRight /></el-icon>
        </button>
        <button
          class="next-action"
          @click="router.push('/datasets')"
        >
          <el-icon><FolderOpened /></el-icon><span><strong>管理知识库</strong><small>组织可检索的业务资料</small></span><el-icon><ArrowRight /></el-icon>
        </button>
        <button
          class="next-action"
          @click="router.push('/chat')"
        >
          <el-icon><ChatDotRound /></el-icon><span><strong>基于证据问答</strong><small>在现有知识库中查找答案</small></span><el-icon><ArrowRight /></el-icon>
        </button>
      </div>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, ChatDotRound, Collection, FolderOpened, Loading, Upload } from '@element-plus/icons-vue'
import { assetApi } from '@/api/asset'
import type { Asset, AssetSourceType } from '@/types/asset'
import { knowledgeApi } from '@/api/knowledge'
import type { KnowledgeItem } from '@/types/knowledge'
import { researchApi } from '@/api/research'
import type { ResearchProject } from '@/types/research'
import { agentApi } from '@/api/agent'
import type { AgentApproval, AgentRun } from '@/types/agent'
import { contentApi } from '@/api/content'
import type { ContentDraft } from '@/types/content'
import { useWorkspaceStore } from '@/stores/workspace'

const router = useRouter()
const workspaceStore = useWorkspaceStore()
const assets = ref<Asset[]>([])
const knowledgeItems = ref<KnowledgeItem[]>([])
const researchProjects = ref<ResearchProject[]>([])
const agentRuns = ref<AgentRun[]>([])
const approvals = ref<AgentApproval[]>([])
const contentDrafts = ref<ContentDraft[]>([])
const assetTotal = ref(0)
const loading = ref(false)
const workspaceId = computed(() => workspaceStore.currentWorkspaceId)
const pendingTasks = computed(() => [
  ...assets.value.filter(asset => ['pending', 'processing', 'failed'].includes(asset.status)).map(asset => ({ id: `asset-${asset.id}`, title: asset.title, label: statusLabel(asset.status), type: statusType(asset.status), route: '/assets' })),
  ...knowledgeItems.value.filter(item => item.review_status === 'draft').map(item => ({ id: `knowledge-${item.id}`, title: item.title, label: '知识待审', type: 'warning' as const, route: '/knowledge' })),
  ...approvals.value.map(item => ({ id: `approval-${item.id}`, title: `Agent 审批 · ${item.step_key || '人工确认'}`, label: '待审批', type: 'warning' as const, route: '/agents' })),
  ...contentDrafts.value.filter(item => item.review_status === 'pending').map(item => ({ id: `content-${item.id}`, title: item.title, label: '草稿待审', type: 'info' as const, route: '/content' }))
].slice(0, 8))
const recentActivities = computed(() => [
  ...assets.value.map(asset => ({ id: `asset-${asset.id}`, title: asset.title, kind: `素材 · ${sourceLabel(asset.source_type)}`, label: statusLabel(asset.status), created_at: asset.created_at })),
  ...knowledgeItems.value.map(item => ({ id: `knowledge-${item.id}`, title: item.title, kind: '知识卡片', label: item.review_status === 'approved' ? '已确认' : '待审核', created_at: item.created_at })),
  ...researchProjects.value.map(project => ({ id: `research-${project.id}`, title: project.name, kind: '研究项目', label: statusLabel(project.status), created_at: project.created_at })),
  ...contentDrafts.value.map(draft => ({ id: `content-${draft.id}`, title: draft.title, kind: '内容草稿', label: reviewLabel(draft.review_status), created_at: draft.created_at }))
].sort((left, right) => new Date(right.created_at || 0).getTime() - new Date(left.created_at || 0).getTime()).slice(0, 8))
const metrics = computed(() => [
  { label: '全部素材', value: assetTotal.value, icon: Collection, tone: 'blue' },
  { label: '处理中', value: assets.value.filter(asset => ['pending', 'processing'].includes(asset.status)).length, icon: Loading, tone: 'orange' },
  { label: '已就绪', value: assets.value.filter(asset => asset.status === 'ready').length, icon: FolderOpened, tone: 'green' },
  { label: '知识卡片', value: knowledgeItems.value.length, icon: FolderOpened, tone: 'green' },
  { label: '待审批', value: approvals.value.length + knowledgeItems.value.filter(item => item.review_status === 'draft').length, icon: Loading, tone: 'orange' },
  { label: '研究项目', value: researchProjects.value.length, icon: Collection, tone: 'blue' },
  { label: 'Agent 运行中', value: agentRuns.value.filter(run => ['queued', 'running', 'waiting_review'].includes(run.status)).length, icon: Loading, tone: 'orange' },
  { label: '失败待处理', value: assets.value.filter(asset => asset.status === 'failed').length + agentRuns.value.filter(run => run.status === 'failed').length, icon: Upload, tone: 'red' }
])
const pipelineStages = computed(() => [
  { key: 'assets', label: '素材', description: '导入与解析', count: assetTotal.value, route: '/assets' },
  { key: 'review', label: '审核', description: '等待人工确认', count: approvals.value.length + knowledgeItems.value.filter(item => item.review_status === 'draft').length + contentDrafts.value.filter(item => item.review_status === 'pending').length, route: '/tasks' },
  { key: 'knowledge', label: '知识', description: '已沉淀卡片', count: knowledgeItems.value.filter(item => item.review_status === 'approved').length, route: '/knowledge' },
  { key: 'research', label: '研究', description: '研究项目', count: researchProjects.value.length, route: '/research' },
  { key: 'publish', label: '发布', description: '内容草稿', count: contentDrafts.value.length, route: '/content' }
])

async function loadDashboard() {
  if (!workspaceId.value) return
  loading.value = true
  const id = workspaceId.value
  const results = await Promise.allSettled([
    assetApi.list(id, { page: 1, page_size: 100 }),
    knowledgeApi.list(id),
    researchApi.listProjects(id),
    agentApi.listRuns(id),
    agentApi.listApprovals(id),
    contentApi.listDrafts(id)
  ])
  const [assetResult, knowledgeResult, researchResult, agentResult, approvalResult, draftResult] = results
  if (assetResult.status === 'fulfilled') {
    assets.value = assetResult.value.items || []
    assetTotal.value = assetResult.value.total ?? assets.value.length
  }
  if (knowledgeResult.status === 'fulfilled') knowledgeItems.value = knowledgeResult.value.items || []
  if (researchResult.status === 'fulfilled') researchProjects.value = researchResult.value.items || []
  if (agentResult.status === 'fulfilled') agentRuns.value = agentResult.value.items || []
  if (approvalResult.status === 'fulfilled') approvals.value = approvalResult.value || []
  if (draftResult.status === 'fulfilled') contentDrafts.value = draftResult.value.items || []
  loading.value = false
}
function sourceLabel(source: AssetSourceType) { return ({ file: '文件', url: '网页', text: '文本', chat: '聊天' }[source] || source) }
function statusLabel(status: string) { return ({ pending: '待处理', processing: '处理中', ready: '已就绪', failed: '失败', active: '进行中', completed: '已完成', cancelled: '已取消', queued: '排队中', running: '运行中' }[status] || status) }
function reviewLabel(status?: string) { return ({ pending: '待审核', approved: '已审核', rejected: '已驳回', draft: '草稿' }[status || ''] || status || '待确认') }
function statusType(status: string): 'success' | 'danger' | 'warning' | 'info' { return status === 'ready' ? 'success' : status === 'failed' ? 'danger' : status === 'processing' ? 'warning' : 'info' }
function formatDate(value?: string | null) { return value ? new Date(value).toLocaleDateString('zh-CN') : '-' }

onMounted(async () => {
  await workspaceStore.fetchCurrentWorkspace()
  await loadDashboard()
})
</script>

<style scoped lang="scss">
.workbench-view { max-width: 1480px; margin: 0 auto; }
.hero { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 30px; padding: 6px 0 4px; }
.eyebrow { margin: 0 0 10px; color: var(--el-color-primary); font-size: 12px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; }
h1 { margin: 0; color: #21182f; font-size: clamp(30px, 3vw, 42px); font-weight: 750; letter-spacing: -.045em; }
.subtitle { max-width: 560px; margin: 12px 0 0; color: #817a8e; font-size: 15px; line-height: 1.7; }
.hero-actions { display: flex; gap: 10px; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 24px 0; }
.metric-card { background: rgba(255,255,255,.78); border: 1px solid rgba(95,74,130,.10); border-radius: 18px; }
.metric-card :deep(.el-card__body) { display: flex; align-items: center; gap: 14px; min-height: 82px; }
.metric-card span { display: block; color: #8b8495; font-size: 12px; }.metric-card strong { display: block; margin-top: 6px; color: #241b31; font-size: 28px; letter-spacing: -.04em; }
.metric-icon { display: grid; width: 44px; height: 44px; place-items: center; border-radius: 14px; font-size: 20px; }.metric-icon.blue { color: #6330d1; background: #f0e8ff; }.metric-icon.orange { color: #ba7216; background: #fff3d7; }.metric-icon.green { color: #2b8b62; background: #e1f6ec; }.metric-icon.red { color: #c74e65; background: #ffe8ee; }
.pipeline-panel { margin-bottom: 18px; border: 1px solid rgba(95,74,130,.10); border-radius: 20px; background: rgba(255,255,255,.78); }.pipeline-panel :deep(.el-card__header) { padding: 17px 20px 14px; border-bottom-color: #f0edf4; }.section-kicker { display: block; margin-bottom: 5px; color: var(--el-color-primary); font-size: 10px; font-weight: 800; letter-spacing: .16em; }.pipeline-track { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 0; }.pipeline-stage { position: relative; display: flex; align-items: center; gap: 10px; min-width: 0; min-height: 82px; padding: 12px 18px 12px 4px; text-align: left; cursor: pointer; border: 0; background: transparent; }.pipeline-stage:hover .stage-copy strong { color: var(--el-color-primary); }.stage-index { display: grid; width: 31px; height: 31px; place-items: center; flex: 0 0 31px; color: #9a8cae; font-size: 10px; font-weight: 800; border: 1px solid #e5def0; border-radius: 50%; background: #faf8fd; }.pipeline-stage.is-active .stage-index { color: #fff; border-color: var(--el-color-primary); background: linear-gradient(135deg,#8f62df,#6134b8); box-shadow: 0 0 0 5px rgba(112,74,198,.09); }.stage-copy { min-width: 0; flex: 1; }.stage-copy strong,.stage-copy small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.stage-copy strong { color: #403449; font-size: 13px; }.stage-copy small { margin-top: 4px; color: #9891a0; font-size: 11px; }.pipeline-stage b { color: #322541; font-family: Georgia,'Times New Roman',serif; font-size: 22px; }.stage-connector { position: absolute; top: 40px; right: -2px; width: 14px; height: 1px; background: #ded5ea; }.stage-connector::after { position: absolute; right: 0; top: -3px; width: 6px; height: 6px; content: ''; border-top: 1px solid #b9a7d3; border-right: 1px solid #b9a7d3; transform: rotate(45deg); }
.content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.panel, .next-panel { border: 1px solid rgba(95,74,130,.10); border-radius: 20px; background: rgba(255,255,255,.78); }
.panel-header { display: flex; justify-content: space-between; align-items: center; color: #2c213b; font-weight: 700; }
.task-item, .recent-item { display: flex; justify-content: space-between; align-items: center; padding: 15px 0; border-bottom: 1px solid #f0edf4; }.task-item:last-child, .recent-item:last-child { border-bottom: 0; }.task-main { display: flex; align-items: center; gap: 10px; color: #41364d; }.task-main .el-icon { color: var(--el-color-primary); }
.recent-item strong, .recent-item span { display: block; }.recent-item strong { color: #403449; font-size: 14px; }.recent-item span { margin-top: 5px; color: #9891a0; font-size: 12px; }
.next-panel { margin-top: 18px; }.next-actions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }.next-action { display: flex; align-items: center; gap: 12px; min-height: 76px; padding: 16px; color: #43364f; text-align: left; cursor: pointer; background: #faf8fd; border: 1px solid #f0ebf7; border-radius: 15px; transition: .2s ease; }.next-action:hover { border-color: #cbb5f4; background: #f7f1ff; transform: translateY(-2px); }.next-action > span { flex: 1; }.next-action strong, .next-action small { display: block; }.next-action strong { color: #30223c; }.next-action small { margin-top: 4px; color: #958b9e; font-size: 12px; }
@media (max-width: 980px) { .metric-grid { grid-template-columns: repeat(2, 1fr); }.pipeline-track { grid-template-columns: repeat(3, minmax(0,1fr)); }.pipeline-stage:nth-child(3) .stage-connector { display: none; } }
@media (max-width: 760px) { .hero { display: block; }.hero-actions { margin-top: 18px; }.content-grid, .next-actions { grid-template-columns: 1fr; }.page-container { padding: 22px 16px; } }
@media (max-width: 760px) { .pipeline-track { grid-template-columns: 1fr; }.pipeline-stage { padding-right: 4px; }.stage-connector { display: none; } }
</style>
