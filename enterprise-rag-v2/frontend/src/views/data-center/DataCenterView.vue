<template>
  <section class="data-center-view">
    <header class="page-header">
      <div>
        <p class="eyebrow">数据中心</p>
        <h1>工作台健康度与效果</h1>
        <p class="subtitle">统一查看素材、知识、研究、Agent 和内容生产的真实状态。</p>
      </div>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </header>
    <el-alert v-if="!workspaceId" type="warning" :closable="false" show-icon>请先选择或创建工作空间。</el-alert>
    <div v-loading="loading" class="metric-grid">
      <el-card v-for="metric in metrics" :key="metric.label" shadow="never" class="metric-card">
        <span>{{ metric.label }}</span><strong>{{ metric.value }}</strong><small>{{ metric.detail }}</small>
      </el-card>
    </div>
    <div class="panel-grid">
      <el-card v-for="section in sections" :key="section.label" shadow="never">
        <template #header><div class="panel-title"><span>{{ section.label }}</span><strong>{{ section.total }}</strong></div></template>
        <div v-if="Object.keys(section.byStatus).length" class="status-list">
          <div v-for="(count, status) in section.byStatus" :key="status"><span>{{ statusLabel(String(status)) }}</span><b>{{ count }}</b></div>
        </div>
        <el-empty v-else description="暂无数据" :image-size="48" />
      </el-card>
    </div>
    <el-card shadow="never" class="health-card">
      <template #header><span>关键健康指标</span></template>
      <div class="health-grid"><div v-for="item in healthMetrics" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div></div>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { dataCenterApi, type DataCenterOverview } from '@/api/dataCenter'
import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()
const loading = ref(false)
const overview = ref<DataCenterOverview | null>(null)
const workspaceId = computed(() => workspaceStore.currentWorkspace?.id || '')
const metrics = computed(() => {
  const value = overview.value
  return [
    { label: '有效素材', value: value?.assets.total ?? 0, detail: '未删除素材' },
    { label: '已审核知识', value: value?.health.approved_knowledge_count ?? 0, detail: '可复用知识卡片' },
    { label: '研究报告', value: value?.health.research_report_count ?? 0, detail: '已生成报告' },
    { label: '内容曝光', value: value?.content_performance.impressions ?? 0, detail: '已回写指标' }
  ]
})
const sections = computed(() => {
  const value = overview.value
  return [
    { label: '素材', total: value?.assets.total ?? 0, byStatus: value?.assets.by_status ?? {} },
    { label: '知识卡片', total: value?.knowledge.total ?? 0, byStatus: value?.knowledge.by_status ?? {} },
    { label: '研究运行', total: value?.research.total ?? 0, byStatus: value?.research.by_status ?? {} },
    { label: 'Agent 运行', total: value?.agents.total ?? 0, byStatus: value?.agents.by_status ?? {} },
    { label: '内容草稿', total: value?.content_drafts.total ?? 0, byStatus: value?.content_drafts.by_status ?? {} }
  ]
})
const healthMetrics = computed(() => {
  const health = overview.value?.health ?? {}
  const rate = (key: string) => `${(Number(health[key] ?? 0) * 100).toFixed(1)}%`
  return [
    { label: '素材处理成功率', value: rate('asset_processing_rate') },
    { label: '知识证据覆盖率', value: rate('knowledge_evidence_coverage') },
    { label: '研究成功率', value: rate('research_success_rate') },
    { label: 'Agent 成功率', value: rate('agent_success_rate') },
    { label: '内容点击率', value: `${((overview.value?.content_performance.click_through_rate ?? 0) * 100).toFixed(1)}%` }
  ]
})
function statusLabel(status: string) { return ({ completed: '已完成', pending: '待处理', processing: '处理中', failed: '失败', draft: '草稿', approved: '已审核', queued: '排队中', running: '运行中' } as Record<string, string>)[status] || status }
async function load() {
  if (!workspaceId.value) return
  loading.value = true
  try { overview.value = await dataCenterApi.overview(workspaceId.value) } catch { ElMessage.error('数据中心加载失败') } finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped lang="scss">
.data-center-view { max-width: 1440px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.eyebrow { margin: 0 0 8px; color: var(--el-color-primary); font-size: 12px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; }
h1 { margin: 0; font-family: Georgia, 'Times New Roman', serif; font-size: clamp(30px, 4vw, 46px); letter-spacing: -.04em; }
.subtitle { max-width: 680px; color: var(--el-text-color-secondary); line-height: 1.7; }
.metric-grid, .panel-grid { display: grid; gap: 16px; margin-top: 20px; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.metric-card, .panel-grid > .el-card, .health-card { border: 1px solid rgba(112, 74, 198, .13); border-radius: 18px; box-shadow: 0 12px 30px rgba(79, 51, 133, .05); }
.metric-card { display: flex; flex-direction: column; gap: 8px; background: linear-gradient(145deg, rgba(255,255,255,.96), rgba(249,247,255,.9)); }
.metric-card span, .metric-card small, .status-list span { color: var(--el-text-color-secondary); }
.metric-card strong { font-size: 28px; }
.panel-grid { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.panel-title, .status-list > div { display: flex; justify-content: space-between; align-items: center; }
.status-list { display: grid; gap: 10px; }
.health-card { margin-top: 18px; }
.health-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 18px; }
.health-grid > div { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; }
.health-grid span { color: var(--el-text-color-secondary); }
.health-grid strong { font-size: 24px; }
@media (max-width: 1000px) { .metric-grid, .panel-grid, .health-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
