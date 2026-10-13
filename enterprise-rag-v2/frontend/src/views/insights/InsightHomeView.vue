<template>
  <section class="insight-home">
    <header class="page-header">
      <div>
        <p class="eyebrow">SOCIAL INSIGHTS · LOCAL EVIDENCE</p>
        <h1>社媒洞察</h1>
        <p class="subtitle">把研究项目、内容选题和已沉淀证据放在同一个观察台，先看问题，再决定下一步行动。</p>
      </div>
      <div class="header-actions">
        <el-button @click="goResearch">新建研究</el-button>
        <el-button type="primary" @click="goContent">进入内容中心</el-button>
      </div>
    </header>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="evidence-alert"
    >当前页面只呈现本工作空间已有的研究与内容证据；未接入外部平台时，不会把推测当成热点事实。</el-alert>

    <div class="insight-metrics">
      <div class="metric-card"><span>研究档案</span><strong>{{ projects.length }}</strong><small>可追溯的问题与来源</small></div>
      <div class="metric-card"><span>已完成研究</span><strong>{{ completedProjects }}</strong><small>可以打开报告核对证据</small></div>
      <div class="metric-card"><span>内容选题</span><strong>{{ topics.length }}</strong><small>可继续转为草稿</small></div>
      <div class="metric-card"><span>待行动</span><strong>{{ actionCount }}</strong><small>研究或草稿仍需推进</small></div>
    </div>

    <el-card shadow="never" class="filter-card">
      <div class="filter-row">
        <el-input v-model="keyword" clearable placeholder="搜索研究主题、问题或描述" class="keyword-input" />
        <el-select v-model="statusFilter" clearable placeholder="全部状态" class="status-select">
          <el-option label="已完成" value="completed" />
          <el-option label="可运行" value="ready" />
          <el-option label="运行中" value="running" />
        </el-select>
        <el-select v-model="platformFilter" clearable placeholder="来源范围" class="status-select">
          <el-option label="有内部样本" value="internal" />
          <el-option label="无内部样本" value="external" />
        </el-select>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </el-card>

    <div class="workspace-grid">
      <el-card shadow="never" class="research-card">
        <template #header>
          <div class="card-heading"><div><span class="section-kicker">RESEARCH ARCHIVE</span><h2>研究档案</h2></div><el-tag effect="plain">{{ filteredProjects.length }} 条</el-tag></div>
        </template>
        <div v-if="filteredProjects.length" class="research-list">
          <article v-for="project in filteredProjects" :key="project.id" class="research-item">
            <div class="item-topline"><el-tag size="small" :type="projectStatusType(projectDisplayStatus(project))">{{ projectStatusLabel(projectDisplayStatus(project)) }}</el-tag><span>{{ sampleLabel(project) }}</span></div>
            <h3>{{ project.name }}</h3>
            <p>{{ project.description || project.questions?.[0]?.question || '暂无研究描述' }}</p>
            <div class="item-actions"><span class="item-meta">{{ formatDate(project.created_at) }}</span><el-button link type="primary" @click="openProject(project)">打开研究 <el-icon><ArrowRight /></el-icon></el-button></div>
          </article>
        </div>
        <el-empty v-else description="暂无匹配的研究档案" :image-size="72" />
      </el-card>

      <div class="side-stack">
        <el-card shadow="never" class="dimension-card">
          <template #header><div class="card-heading"><div><span class="section-kicker">EVIDENCE DESK</span><h2>洞察维度</h2></div><el-button link type="primary" @click="goResearch">去研究</el-button></div></template>
          <div class="dimension-list">
            <button v-for="dimension in dimensions" :key="dimension.label" class="dimension-item" type="button" @click="focusDimension(dimension.label)">
              <span class="dimension-icon"><el-icon><component :is="dimension.icon" /></el-icon></span><span><strong>{{ dimension.label }}</strong><small>{{ dimension.detail }}</small></span><b>{{ dimension.count }}</b>
            </button>
          </div>
        </el-card>

        <el-card shadow="never" class="action-card">
          <template #header><div class="card-heading"><div><span class="section-kicker">NEXT ACTION</span><h2>从洞察到行动</h2></div></div></template>
          <div class="action-list">
            <button type="button" @click="goResearch"><span class="action-index">01</span><span><strong>先验证一个问题</strong><small>绑定内部知识库，生成可核对的证据包</small></span><el-icon><ArrowRight /></el-icon></button>
            <button type="button" @click="goContent"><span class="action-index">02</span><span><strong>把结论变成选题</strong><small>进入内容中心生成草稿并提交审核</small></span><el-icon><ArrowRight /></el-icon></button>
            <button type="button" @click="goKnowledge"><span class="action-index">03</span><span><strong>沉淀可复用知识</strong><small>回到知识中心检查证据和审核状态</small></span><el-icon><ArrowRight /></el-icon></button>
          </div>
        </el-card>
      </div>
    </div>

    <el-card shadow="never" class="topics-card">
      <template #header><div class="card-heading"><div><span class="section-kicker">TOPIC SIGNALS</span><h2>内容信号</h2></div><el-button link type="primary" @click="goContent">查看全部</el-button></div></template>
      <div v-if="topics.length" class="topic-grid">
        <button v-for="topic in topics.slice(0, 6)" :key="topic.id" class="topic-item" type="button" @click="goContent"><span class="topic-dot" /><span><strong>{{ topic.title }}</strong><small>{{ topic.brief || '暂无选题说明' }}</small></span><el-icon><ArrowRight /></el-icon></button>
      </div>
      <el-empty v-else description="还没有内容选题，可从研究结论开始创建" :image-size="64" />
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ArrowRight, ChatDotRound, DataAnalysis, Document, Opportunity, TrendCharts } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { researchApi } from '@/api/research'
import { contentApi } from '@/api/content'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ResearchProject } from '@/types/research'
import type { ContentDraft, ContentTopic } from '@/types/content'

const router = useRouter()
const workspaceStore = useWorkspaceStore()
const projects = ref<ResearchProject[]>([])
const topics = ref<ContentTopic[]>([])
const drafts = ref<ContentDraft[]>([])
const latestRunStatuses = ref<Record<string, string>>({})
const keyword = ref('')
const statusFilter = ref('')
const platformFilter = ref('')

const completedProjects = computed(() => projects.value.filter(item => projectDisplayStatus(item) === 'completed').length)
const actionCount = computed(() => projects.value.filter(item => projectDisplayStatus(item) !== 'completed').length + drafts.value.filter(item => item.status === 'pending').length)
const filteredProjects = computed(() => projects.value.filter((project) => {
  const text = `${project.name} ${project.description || ''} ${project.questions?.map(item => item.question).join(' ') || ''}`.toLowerCase()
  const matchesKeyword = !keyword.value.trim() || text.includes(keyword.value.trim().toLowerCase())
  const matchesStatus = !statusFilter.value || projectDisplayStatus(project) === statusFilter.value
  const hasInternal = project.sample_count > 0
  const matchesPlatform = !platformFilter.value || (platformFilter.value === 'internal' ? hasInternal : !hasInternal)
  return matchesKeyword && matchesStatus && matchesPlatform
}))
const dimensions = computed(() => [
  { label: '用户需求', detail: '研究问题与选题', count: projects.value.length, icon: Opportunity },
  { label: '观点与评论', detail: '待继续采集的讨论', count: topics.value.length, icon: ChatDotRound },
  { label: '证据摘录', detail: '内部研究可核对', count: completedProjects.value, icon: Document },
  { label: '趋势信号', detail: '内容与数据表现', count: drafts.value.length, icon: TrendCharts }
])

function formatDate(value?: string) { return value ? new Date(value).toLocaleDateString('zh-CN') : '最近更新' }
function sampleLabel(project: ResearchProject) { return `${project.sample_count || 0} 个样本 · ${project.questions?.length || 0} 个问题` }
function projectDisplayStatus(project: ResearchProject) {
  return latestRunStatuses.value[project.id] || project.status
}
function projectStatusLabel(status: string) { return ({ completed: '已完成', ready: '可运行', running: '运行中', failed: '失败' } as Record<string, string>)[status] || status || '待处理' }
function projectStatusType(status: string) { return status === 'completed' ? 'success' : status === 'failed' ? 'danger' : status === 'running' ? 'warning' : 'info' }
function resetFilters() { keyword.value = ''; statusFilter.value = ''; platformFilter.value = '' }
function focusDimension(label: string) {
  if (label === '证据摘录') {
    statusFilter.value = 'completed'
    ElMessage.success('已筛选出完成研究，可打开报告核对证据')
    return
  }
  if (label === '用户需求') {
    statusFilter.value = 'ready'
    ElMessage.success('已筛选出可运行的研究问题')
    return
  }
  if (label === '观点与评论') {
    document.querySelector('.topics-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    ElMessage.info('已定位到内容信号')
    return
  }
  router.push('/content')
}
function goResearch() { router.push('/research') }
function goContent() { router.push('/content') }
function goKnowledge() { router.push('/knowledge') }
function openProject(project: ResearchProject) { router.push(`/insights/${project.id}`) }

async function load() {
  const workspaceId = workspaceStore.currentWorkspaceId
  if (!workspaceId) return
  try {
    const [projectResult, topicResult, draftResult] = await Promise.allSettled([
      researchApi.listProjects(workspaceId),
      contentApi.listTopics(workspaceId),
      contentApi.listDrafts(workspaceId)
    ])
    projects.value = projectResult.status === 'fulfilled' ? projectResult.value.items || [] : []
    topics.value = topicResult.status === 'fulfilled' ? topicResult.value.items || [] : []
    drafts.value = draftResult.status === 'fulfilled' ? draftResult.value.items || [] : []
    const runEntries = await Promise.allSettled(projects.value.map(async project => [project.id, (await researchApi.listRuns(project.id)).items || []] as const))
    const statuses: Record<string, string> = {}
    for (const entry of runEntries) {
      if (entry.status !== 'fulfilled' || !entry.value[1].length) continue
      const latest = [...entry.value[1]].sort((left, right) =>
        new Date(right.created_at || right.updated_at).getTime() - new Date(left.created_at || left.updated_at).getTime()
      )[0]
      if (latest?.status) statuses[entry.value[0]] = latest.status
    }
    latestRunStatuses.value = statuses
    if ([projectResult, topicResult, draftResult].some(result => result.status === 'rejected') || runEntries.some(result => result.status === 'rejected')) {
      ElMessage.warning('部分洞察数据暂时不可用，已保留可加载内容')
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '社媒洞察加载失败')
  }
}

onMounted(async () => { await workspaceStore.fetchCurrentWorkspace(); await load() })
</script>

<style scoped lang="scss">
.insight-home { max-width: 1440px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; margin-bottom: 22px; }
.header-actions { display: flex; gap: 10px; padding-top: 18px; }
.eyebrow, .section-kicker { color: var(--el-color-primary); font-size: 11px; font-weight: 800; letter-spacing: .16em; }
.eyebrow { margin: 0 0 8px; }
h1, h2, h3, p { margin-top: 0; }
h1 { margin-bottom: 8px; color: var(--el-text-color-primary); font-family: Georgia, 'Times New Roman', serif; font-size: clamp(32px, 4vw, 48px); letter-spacing: -.045em; }
.subtitle { max-width: 720px; margin-bottom: 0; color: var(--el-text-color-secondary); line-height: 1.75; }
.evidence-alert { margin-bottom: 18px; border: 1px solid rgba(112,74,198,.14); border-radius: 14px; background: #faf8ff; }
.insight-metrics { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; margin-bottom: 18px; }
.metric-card, .filter-card, .research-card, .dimension-card, .action-card, .topics-card { border: 1px solid rgba(112,74,198,.13); border-radius: 18px; background: linear-gradient(145deg, rgba(255,255,255,.96), rgba(249,247,255,.9)); box-shadow: 0 12px 30px rgba(79,51,133,.05); }
.metric-card { display: flex; flex-direction: column; gap: 6px; padding: 18px 20px; }
.metric-card span, .metric-card small, .item-topline span, .item-meta, .dimension-item small, .action-list small, .topic-item small { color: var(--el-text-color-secondary); }
.metric-card strong { color: var(--el-color-primary); font-family: Georgia, 'Times New Roman', serif; font-size: 31px; }
.filter-card { margin-bottom: 18px; }
.filter-card :deep(.el-card__body) { padding: 14px; }
.filter-row { display: flex; gap: 10px; }
.keyword-input { flex: 1; }
.status-select { width: 160px; }
.workspace-grid { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(340px, .8fr); gap: 18px; align-items: start; }
.side-stack { display: grid; gap: 18px; }
.card-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.card-heading h2 { margin: 5px 0 0; font-size: 20px; letter-spacing: -.025em; }
.research-list { display: grid; gap: 10px; }
.research-item { padding: 16px; border: 1px solid rgba(112,74,198,.1); border-radius: 14px; background: rgba(255,255,255,.68); transition: border-color .2s, transform .2s; }
.research-item:hover { border-color: rgba(112,74,198,.3); transform: translateY(-1px); }
.item-topline, .item-actions { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.research-item h3 { margin: 12px 0 6px; font-size: 17px; }
.research-item p { min-height: 24px; margin-bottom: 12px; color: var(--el-text-color-secondary); line-height: 1.6; }
.item-actions { border-top: 1px solid rgba(112,74,198,.08); padding-top: 10px; }
.dimension-list, .action-list { display: grid; gap: 8px; }
.dimension-item, .action-list button, .topic-item { display: flex; width: 100%; align-items: center; gap: 12px; padding: 11px 0; border: 0; border-bottom: 1px solid rgba(112,74,198,.08); text-align: left; background: transparent; cursor: pointer; }
.dimension-item:last-child, .action-list button:last-child, .topic-item:last-child { border-bottom: 0; }
.dimension-item > span:nth-child(2), .action-list button > span:nth-child(2), .topic-item > span:nth-child(2) { flex: 1; display: flex; flex-direction: column; gap: 3px; }
.dimension-item strong, .action-list strong, .topic-item strong { color: var(--el-text-color-primary); font-size: 14px; }
.dimension-item b { color: var(--el-color-primary); font-size: 18px; }
.dimension-icon { display: grid; width: 34px; height: 34px; place-items: center; border-radius: 10px; color: var(--el-color-primary); background: #f0eaff; }
.action-index { color: var(--el-color-primary); font-size: 11px; font-weight: 800; letter-spacing: .1em; }
.action-list button:hover strong, .topic-item:hover strong { color: var(--el-color-primary); }
.topics-card { margin-top: 18px; }
.topic-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 0 24px; }
.topic-dot { width: 8px; height: 8px; flex: 0 0 8px; border-radius: 50%; background: var(--el-color-primary); box-shadow: 0 0 0 5px #f0eaff; }
@media (max-width: 1000px) { .insight-metrics { grid-template-columns: repeat(2, minmax(0,1fr)); } .workspace-grid { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .page-header, .filter-row { flex-direction: column; } .header-actions { padding-top: 0; } .status-select { width: 100%; } .topic-grid { grid-template-columns: 1fr; } }
</style>
