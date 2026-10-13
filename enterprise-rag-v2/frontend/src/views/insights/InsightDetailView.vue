<template>
  <section class="insight-detail">
    <div class="topbar">
      <el-button text @click="router.push('/insights')">← 返回社媒洞察</el-button>
      <div class="top-actions">
        <el-button :loading="loading" @click="load">刷新证据</el-button>
        <el-button type="primary" @click="router.push('/research')">进入研究工作台</el-button>
      </div>
    </div>

    <el-skeleton v-if="loading && !project" :rows="8" animated />
    <template v-else-if="project">
      <header class="detail-header">
        <div>
          <div class="status-line"><el-tag size="small" :type="statusType(displayStatus)">{{ statusLabel(displayStatus) }}</el-tag><span>{{ formatDate(project?.updated_at || project?.created_at) }} · {{ project?.sample_count || 0 }} 个样本</span></div>
          <p class="eyebrow">SOCIAL INSIGHTS · EVIDENCE REVIEW</p>
          <h1>{{ project?.name || '洞察档案' }}</h1>
          <p class="subtitle">{{ project?.description || project?.questions?.[0]?.question || '围绕研究问题整理用户需求、证据和可行动结论。' }}</p>
        </div>
        <div class="header-stats"><div><strong>{{ findings.length }}</strong><span>主要发现</span></div><div><strong>{{ evidence.length }}</strong><span>证据摘录</span></div><div><strong>{{ latestRun?.progress || 0 }}%</strong><span>运行进度</span></div></div>
      </header>

      <el-alert v-if="errorMessage" type="warning" :closable="false" show-icon class="state-alert">{{ errorMessage }}</el-alert>

      <el-card shadow="never" class="detail-card">
        <el-tabs v-model="activeTab">
          <el-tab-pane name="needs"><template #label>需求 <el-badge :value="questions.length" :max="99" /></template>
            <div class="tab-intro">研究问题是本档案的入口，后续结论和证据都应能回到具体问题。</div>
            <div v-if="questions.length" class="question-grid"><article v-for="(question, index) in questions" :key="`${question.question}-${index}`" class="question-card"><span>问题 {{ String(index + 1).padStart(2, '0') }}</span><h3>{{ question.question }}</h3><small>排序 {{ question.sort_order + 1 }}</small></article></div>
            <el-empty v-else description="还没有记录研究问题" :image-size="64" />
          </el-tab-pane>

          <el-tab-pane name="findings"><template #label>观点 <el-badge :value="findings.length" :max="99" /></template>
            <div class="tab-intro">只展示已有研究运行产生的发现；每条发现都标记置信度和证据数量。</div>
            <div v-if="findings.length" class="finding-grid"><article v-for="finding in findings" :key="finding.id" class="finding-card"><div class="finding-top"><el-tag size="small" :type="finding.needs_review ? 'warning' : 'success'">{{ finding.needs_review ? '待核验' : '已提取' }}</el-tag><span>置信度 {{ Math.round(finding.confidence * 100) }}% · {{ finding.evidence_ids.length }} 条证据</span></div><h3>{{ finding.claim }}</h3><p>{{ finding.claim_type || '研究发现' }} · {{ finding.review_status }}</p></article></div>
            <el-empty v-else description="运行完成后，研究发现会出现在这里" :image-size="64" />
          </el-tab-pane>

          <el-tab-pane name="replies"><template #label>评论回复 <el-badge :value="replySignals.length" :max="99" /></template>
            <div class="tab-intro">这里把当前研究中可继续追问的评论信号独立出来，避免把“有讨论”误当成“已验证结论”。</div>
            <div v-if="replySignals.length" class="signal-list"><div v-for="signal in replySignals" :key="signal.id" class="signal-row"><span class="signal-mark">↗</span><div><strong>{{ signal.title }}</strong><p>{{ signal.detail }}</p></div><el-button link type="primary" @click="activeTab = 'evidence'">查看证据</el-button></div></div>
            <el-empty v-else description="当前研究没有独立的评论回复数据，先从证据摘录继续核对" :image-size="64" />
          </el-tab-pane>

          <el-tab-pane name="platform"><template #label>平台差异</template>
            <div class="tab-intro">平台差异需要真实平台采集数据支撑。当前系统不会用静态数字填充未接入的平台。</div>
            <div class="platform-empty"><div class="empty-orbit">◎</div><h3>等待平台连接器或导入快照</h3><p>可以前往平台数据页配置连接器，或导入平台后台导出的指标快照，再回到这里比较来源、互动和内容表现。</p><el-button type="primary" plain @click="router.push('/platform-data')">打开平台数据</el-button></div>
          </el-tab-pane>

          <el-tab-pane name="evidence"><template #label>证据摘录 <el-badge :value="evidence.length" :max="99" /></template>
            <div class="tab-intro">每条证据都保留来源标题、定位和原文摘录，便于从结论回看原始材料。</div>
            <div v-if="evidence.length" class="evidence-list"><article v-for="item in evidence" :key="item.id" class="evidence-card"><div class="evidence-label"><span>证据 {{ evidence.indexOf(item) + 1 }}</span><small>{{ item.locator || '未记录定位' }}</small></div><blockquote>{{ item.quote }}</blockquote><div class="evidence-source"><strong>{{ item.source_title || '未命名来源' }}</strong><a v-if="item.source_uri" :href="item.source_uri" target="_blank" rel="noreferrer">打开来源 ↗</a></div></article></div>
            <el-empty v-else description="当前研究还没有证据摘录" :image-size="64" />
          </el-tab-pane>

          <el-tab-pane name="boundary"><template #label>样本与边界</template>
            <div class="boundary-grid"><div><span class="section-kicker">SAMPLE</span><strong>{{ project?.sample_count || 0 }}</strong><p>当前研究样本数量</p></div><div><span class="section-kicker">QUESTIONS</span><strong>{{ questions.length }}</strong><p>研究问题数量</p></div><div><span class="section-kicker">RUN</span><strong>{{ latestRun ? statusLabel(latestRun.status) : '未运行' }}</strong><p>{{ latestRun?.current_stage || '等待研究运行' }}</p></div></div>
            <el-alert type="info" :closable="false" show-icon>样本数量为 0 时，当前档案只能作为问题草稿，不能代表真实平台趋势；报告发布前仍需完成人工审核。</el-alert>
          </el-tab-pane>
        </el-tabs>
      </el-card>

      <el-card shadow="never" class="report-card">
        <template #header><div class="card-heading"><div><span class="section-kicker">REPORT</span><h2>研究报告</h2></div><div class="report-header-actions"><el-tag effect="plain">{{ report?.review_status || '尚未生成' }}</el-tag><el-button v-if="report?.content_markdown" size="small" @click="reportDialog = true">阅读原报告</el-button><el-button v-if="report?.content_markdown" size="small" type="primary" plain @click="presentationMode = true">进入演示模式</el-button></div></div></template>
        <pre v-if="report?.content_markdown" class="report-content">{{ report.content_markdown }}</pre>
        <el-empty v-else description="完成一次研究运行后，报告会在这里展示" :image-size="64" />
      </el-card>
    </template>
    <el-empty v-else-if="errorMessage" description="研究档案不存在或当前账号无权访问" :image-size="80"><el-button type="primary" @click="router.push('/insights')">返回社媒洞察</el-button></el-empty>

    <el-dialog v-model="reportDialog" title="研究报告审核台" width="860px" destroy-on-close>
      <el-alert v-if="report?.content_json?.evidence_only === true" type="info" :closable="false" show-icon class="report-alert">当前报告为证据包，结论仍需人工审核后才能沉淀或转为内容。</el-alert>
      <el-alert v-if="reportActionError" type="warning" :closable="false" show-icon class="report-alert">{{ reportActionError }}</el-alert>
      <pre v-if="report?.content_markdown" class="report-dialog-content">{{ report.content_markdown }}</pre>
      <el-form v-if="report?.review_status === 'approved' && !report.published_dataset_id" label-position="top" class="publish-form">
        <el-form-item label="发布到知识库（可选）"><el-select v-model="publishDatasetId" clearable filterable placeholder="选择当前工作空间的知识库" style="width:100%"><el-option v-for="dataset in datasets" :key="dataset.id" :label="dataset.name" :value="dataset.id" /></el-select></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reportDialog = false">关闭</el-button>
        <el-button v-if="report && report.review_status !== 'approved'" type="danger" plain :loading="reportActionLoading" @click="reviewReport('rejected')">驳回</el-button>
        <el-button v-if="report && report.review_status !== 'approved'" type="primary" :loading="reportActionLoading" @click="reviewReport('approved')">审核通过</el-button>
        <el-button v-if="report?.review_status === 'approved' && !report.published_knowledge_item_id" type="success" plain :loading="reportActionLoading" @click="publishToKnowledge">沉淀为知识卡片</el-button>
        <el-button v-if="report?.review_status === 'approved' && !report.published_dataset_id" type="success" :disabled="!publishDatasetId" :loading="reportActionLoading" @click="publishReport">发布到知识库</el-button>
        <el-button v-if="report?.review_status === 'approved'" type="warning" plain :loading="reportActionLoading" @click="createContentDraft">生成内容草稿</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="presentationMode" title="研究报告 · 演示模式" fullscreen class="presentation-dialog">
      <div class="presentation-page"><p class="eyebrow">SOCIAL INSIGHTS · PRESENTATION</p><h1>{{ project?.name || '研究报告' }}</h1><p class="presentation-subtitle">{{ project?.description || '基于可追溯证据整理的研究结论。' }}</p><pre v-if="report?.content_markdown" class="presentation-content">{{ report.content_markdown }}</pre><el-empty v-else description="暂无可演示的报告内容" /></div>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { researchApi } from '@/api/research'
import { contentApi } from '@/api/content'
import { getDatasets } from '@/api/dataset'
import { useWorkspaceStore } from '@/stores/workspace'
import type { ResearchEvidence, ResearchFinding, ResearchProject, ResearchReport, ResearchRun } from '@/types/research'

const route = useRoute(); const router = useRouter(); const projectId = computed(() => String(route.params.projectId || ''))
const workspaceStore = useWorkspaceStore()
const loading = ref(false); const project = ref<ResearchProject | null>(null); const runs = ref<ResearchRun[]>([]); const report = ref<ResearchReport | null>(null); const findings = ref<ResearchFinding[]>([]); const evidence = ref<ResearchEvidence[]>([]); const activeTab = ref('needs'); const errorMessage = ref(''); const reportDialog = ref(false); const presentationMode = ref(false); const reportActionLoading = ref(false); const reportActionError = ref(''); const publishDatasetId = ref(''); const datasets = ref<Array<{ id: string; name: string }>>([])
const questions = computed(() => project.value?.questions || [])
const latestRun = computed(() => [...runs.value].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())[0])
const displayStatus = computed(() => latestRun.value?.status || project.value?.status || '')
const replySignals = computed(() => findings.value.filter(item => item.claim_type?.toLowerCase().includes('comment') || item.claim_type?.includes('评论')).map(item => ({ id: item.id, title: item.claim, detail: `${item.evidence_ids.length} 条证据支持，置信度 ${Math.round(item.confidence * 100)}%` })))
function formatDate(value?: string) { return value ? new Date(value).toLocaleDateString('zh-CN') : '最近更新' }
function statusLabel(status?: string) { return ({ completed: '已完成', active: '可运行', ready: '可运行', running: '运行中', failed: '失败', cancelled: '已取消' } as Record<string, string>)[status || ''] || status || '待处理' }
function statusType(status?: string) { return status === 'completed' ? 'success' : status === 'failed' ? 'danger' : status === 'running' ? 'warning' : 'info' }
async function loadDatasets() { const workspaceId = workspaceStore.currentWorkspaceId; if (!workspaceId) return; try { const result = await getDatasets({ workspace_id: workspaceId, page: 1, page_size: 100 }); const items = Array.isArray(result) ? result : result?.items || result?.data?.items || []; datasets.value = items.map((item: { id: string; name: string }) => ({ id: item.id, name: item.name })) } catch { datasets.value = [] } }
async function reviewReport(reviewStatus: 'approved' | 'rejected') { if (!report.value) return; reportActionLoading.value = true; reportActionError.value = ''; try { report.value = await researchApi.reviewReport(report.value.id, reviewStatus); if (reviewStatus === 'approved') await loadDatasets(); ElMessage.success(reviewStatus === 'approved' ? '报告已审核通过' : '报告已驳回') } catch (error) { reportActionError.value = error instanceof Error ? error.message : '报告审核失败' } finally { reportActionLoading.value = false } }
async function publishToKnowledge() { if (!report.value) return; reportActionLoading.value = true; reportActionError.value = ''; try { report.value = await researchApi.publishToKnowledge(report.value.id); ElMessage.success('报告已沉淀为待审核知识卡片') } catch (error) { reportActionError.value = error instanceof Error ? error.message : '报告沉淀失败' } finally { reportActionLoading.value = false } }
async function publishReport() { if (!report.value || !publishDatasetId.value) return; reportActionLoading.value = true; reportActionError.value = ''; try { report.value = await researchApi.publishReport(report.value.id, publishDatasetId.value); ElMessage.success('报告已发布到知识库处理队列') } catch (error) { reportActionError.value = error instanceof Error ? error.message : '报告发布失败' } finally { reportActionLoading.value = false } }
async function createContentDraft() { if (!report.value) return; reportActionLoading.value = true; reportActionError.value = ''; try { await contentApi.createDraftFromResearch(report.value.id); ElMessage.success('内容草稿已生成，可在内容中心继续编辑') } catch (error) { reportActionError.value = error instanceof Error ? error.message : '内容草稿生成失败' } finally { reportActionLoading.value = false } }
async function load() {
  if (!projectId.value) return
  loading.value = true
  errorMessage.value = ''
  findings.value = []
  evidence.value = []
  report.value = null
  try {
    await workspaceStore.fetchCurrentWorkspace()
    const workspaceId = workspaceStore.currentWorkspaceId
    if (!workspaceId) throw new Error('当前没有可用工作空间')
    const projectResult = await researchApi.listProjects(workspaceId)
    project.value = projectResult.items?.find(item => item.id === projectId.value) || null
    if (!project.value) throw new Error('找不到该研究档案')
    runs.value = (await researchApi.listRuns(projectId.value)).items || []
    const run = latestRun.value
    if (!run) return
    const [findingResult, evidenceResult] = await Promise.allSettled([
      researchApi.listRunFindings(run.id),
      researchApi.listRunEvidence(run.id)
    ])
    findings.value = findingResult.status === 'fulfilled' ? findingResult.value || [] : []
    evidence.value = evidenceResult.status === 'fulfilled' ? evidenceResult.value || [] : []
    const partialFailure = findingResult.status === 'rejected' || evidenceResult.status === 'rejected'
    if (run.status === 'failed') {
      errorMessage.value = run.error_message || '最近一次研究运行失败，请回到研究工作台检查配置后重试'
    } else if (partialFailure) {
      errorMessage.value = '部分证据数据暂时不可用，当前页面仍保留可加载内容'
    }
    if (run.report_id || run.status === 'completed') {
      try {
        report.value = await researchApi.getReport(run.id)
        publishDatasetId.value = report.value.published_dataset_id || ''
        if (report.value.review_status === 'approved' && !report.value.published_dataset_id) await loadDatasets()
      } catch {
        report.value = null
        errorMessage.value = errorMessage.value || '研究报告暂时不可用，请刷新后重试'
      }
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '洞察档案加载失败'
    ElMessage.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<style scoped lang="scss">
.insight-detail{max-width:1440px;margin:0 auto}.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.top-actions{display:flex;gap:10px}.detail-header{display:flex;justify-content:space-between;align-items:flex-end;gap:28px;padding:20px 0 28px;border-bottom:1px solid rgba(112,74,198,.12)}.status-line{display:flex;align-items:center;gap:10px;margin-bottom:18px;color:var(--el-text-color-secondary);font-size:13px}.eyebrow,.section-kicker{color:var(--el-color-primary);font-size:11px;font-weight:800;letter-spacing:.16em}.eyebrow{margin:0 0 8px}h1{margin:0 0 10px;font-family:Georgia,'Times New Roman',serif;font-size:clamp(32px,4vw,52px);letter-spacing:-.05em}.subtitle{max-width:760px;margin:0;color:var(--el-text-color-secondary);line-height:1.75}.header-stats{display:grid;grid-template-columns:repeat(3,110px);gap:10px}.header-stats div{display:flex;flex-direction:column;gap:5px;padding:14px;border:1px solid rgba(112,74,198,.13);border-radius:14px;background:#fbfaff}.header-stats strong{font-family:Georgia,'Times New Roman',serif;font-size:24px;color:var(--el-color-primary)}.header-stats span{color:var(--el-text-color-secondary);font-size:12px}.state-alert{margin:18px 0}.detail-card,.report-card{margin-top:18px;border:1px solid rgba(112,74,198,.13);border-radius:18px;background:linear-gradient(145deg,rgba(255,255,255,.96),rgba(249,247,255,.9));box-shadow:0 12px 30px rgba(79,51,133,.05)}.detail-card :deep(.el-card__body){padding:8px 22px 24px}.tab-intro{margin:10px 0 18px;color:var(--el-text-color-secondary);line-height:1.7}.question-grid,.finding-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.question-card,.finding-card{padding:16px;border:1px solid rgba(112,74,198,.1);border-radius:14px;background:rgba(255,255,255,.7)}.question-card>span{color:var(--el-color-primary);font-size:11px;font-weight:800;letter-spacing:.12em}.question-card h3,.finding-card h3{margin:12px 0 8px;line-height:1.55}.question-card small,.finding-card p{color:var(--el-text-color-secondary)}.finding-top,.evidence-source{display:flex;justify-content:space-between;align-items:center;gap:12px}.finding-top span,.evidence-label small{color:var(--el-text-color-secondary);font-size:12px}.signal-list,.evidence-list{display:grid;gap:10px}.signal-row{display:flex;align-items:center;gap:12px;padding:14px;border-bottom:1px solid rgba(112,74,198,.1)}.signal-row>div{flex:1}.signal-row p{margin:5px 0 0;color:var(--el-text-color-secondary)}.signal-mark{display:grid;width:32px;height:32px;place-items:center;border-radius:10px;color:var(--el-color-primary);background:#f0eaff}.platform-empty{text-align:center;padding:44px 20px}.empty-orbit{display:grid;width:64px;height:64px;place-items:center;margin:0 auto 16px;border:1px solid rgba(112,74,198,.25);border-radius:50%;color:var(--el-color-primary);font-size:34px;background:#f4efff}.platform-empty h3{margin:0 0 8px}.platform-empty p{max-width:560px;margin:0 auto 18px;color:var(--el-text-color-secondary);line-height:1.7}.evidence-card{padding:16px;border:1px solid rgba(112,74,198,.1);border-radius:14px;background:rgba(255,255,255,.7)}.evidence-label{display:flex;justify-content:space-between;color:var(--el-color-primary);font-size:12px;font-weight:800;letter-spacing:.08em}.evidence-card blockquote{margin:14px 0;padding:14px 16px;border-left:3px solid var(--el-color-primary);background:#faf8ff;line-height:1.75;white-space:pre-wrap}.evidence-source strong{font-size:13px}.evidence-source a{color:var(--el-color-primary);font-size:12px}.boundary-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:8px 0 20px}.boundary-grid>div{padding:18px;border:1px solid rgba(112,74,198,.1);border-radius:14px;background:#fbfaff}.boundary-grid strong{display:block;margin:12px 0 5px;font-family:Georgia,'Times New Roman',serif;font-size:28px;color:var(--el-color-primary)}.boundary-grid p{margin:0;color:var(--el-text-color-secondary);font-size:13px}.report-card :deep(.el-card__body){padding-top:8px}.card-heading{display:flex;justify-content:space-between;align-items:flex-start}.card-heading h2{margin:5px 0 0;font-size:20px}.report-content{max-height:480px;overflow:auto;margin:12px 0 0;padding:18px;border:1px solid rgba(112,74,198,.1);border-radius:12px;background:#fbfaff;white-space:pre-wrap;word-break:break-word;font:inherit;line-height:1.75}@media(max-width:900px){.detail-header{display:block}.header-stats{margin-top:20px;grid-template-columns:repeat(3,1fr)}.question-grid,.finding-grid{grid-template-columns:1fr}}@media(max-width:620px){.topbar{align-items:flex-start;flex-direction:column;gap:10px}.top-actions{flex-wrap:wrap}.header-stats{grid-template-columns:repeat(3,minmax(0,1fr))}.header-stats div{padding:10px}.boundary-grid{grid-template-columns:1fr}.detail-card :deep(.el-card__body){padding-left:12px;padding-right:12px}}
.report-header-actions{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:8px}.report-alert{margin-bottom:14px}.publish-form{margin-top:16px}.report-dialog-content,.presentation-content{max-height:55vh;overflow:auto;margin:12px 0 0;padding:18px;border:1px solid rgba(112,74,198,.1);border-radius:12px;background:#fbfaff;white-space:pre-wrap;word-break:break-word;font:inherit;line-height:1.75}.presentation-dialog :deep(.el-dialog__body){padding:0;background:#f8f6fc}.presentation-page{min-height:calc(100vh - 110px);padding:56px clamp(24px,8vw,140px);background:linear-gradient(145deg,#fff,#f4efff)}.presentation-page h1{max-width:1000px;font-size:clamp(38px,6vw,76px)}.presentation-subtitle{max-width:760px;color:var(--el-text-color-secondary);font-size:18px;line-height:1.8}.presentation-content{max-height:none;margin-top:34px;padding:28px;background:rgba(255,255,255,.8);font-size:18px;line-height:2}@media(max-width:620px){.report-header-actions{justify-content:flex-start}.presentation-page{padding:32px 18px}.presentation-content{font-size:15px}}
</style>
