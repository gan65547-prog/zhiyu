<template>
  <section class="home-view">
    <template v-if="authStore.isSuperuser">
      <div class="admin-shell">
        <p class="eyebrow">TENANT CONTROL CENTER</p>
        <h1>管理后台总览</h1>
        <p>统一管理租户、用量与系统配置。</p>
        <el-button type="primary" size="large" @click="router.push('/tenants')">
          <el-icon><OfficeBuilding /></el-icon>进入租户管理
        </el-button>
      </div>
    </template>

    <template v-else>
      <header class="dashboard-hero">
        <div>
          <p class="eyebrow">PERSONAL AI WORKBENCH · {{ workspaceStore.currentWorkspace?.name || '当前工作空间' }}</p>
          <h1>工作台总览</h1>
          <p class="hero-copy">让素材、知识、研究和内容生产在同一个工作流里持续沉淀。</p>
        </div>
        <div class="hero-actions">
          <el-button type="primary" size="large" @click="router.push('/assets')"><el-icon><Upload /></el-icon>导入素材</el-button>
          <el-button size="large" @click="router.push('/chat')"><el-icon><ChatDotRound /></el-icon>开始问答</el-button>
        </div>
      </header>

      <div class="status-strip">
        <span><i class="status-dot" />本地工作区已连接</span>
        <span>知识库与内容数据实时读取</span>
        <el-button link @click="router.push('/workbench')">查看完整工作台 <el-icon><ArrowRight /></el-icon></el-button>
      </div>

      <div class="metric-grid">
        <button class="metric-card" @click="router.push('/datasets')"><span>知识库</span><strong>{{ stats.datasets }}</strong><small>可检索的资料空间</small><el-icon><FolderOpened /></el-icon></button>
        <button class="metric-card" @click="router.push('/assets')"><span>文档与素材</span><strong>{{ stats.documents }}</strong><small>已纳入当前工作区</small><el-icon><Document /></el-icon></button>
        <button class="metric-card" @click="router.push('/workspaces')"><span>工作空间</span><strong>{{ stats.workspaces }}</strong><small>可协作的上下文</small><el-icon><Setting /></el-icon></button>
        <button class="metric-card is-accent" @click="router.push('/chat')"><span>历史对话</span><strong>{{ stats.chats }}</strong><small>可继续追问与复用</small><el-icon><ChatLineSquare /></el-icon></button>
      </div>

      <div class="dashboard-grid">
        <el-card shadow="never" class="dashboard-card">
          <template #header><div class="card-heading"><div><span class="section-kicker">KNOWLEDGE BASE</span><h2>知识沉淀状态</h2></div><el-button link @click="router.push('/knowledge')">打开知识中心 <el-icon><ArrowRight /></el-icon></el-button></div></template>
          <div class="health-visual"><div class="health-ring"><strong>{{ stats.documents ? '已连接' : '待建立' }}</strong><span>{{ stats.documents ? `${stats.documents} 份资料` : '从导入素材开始' }}</span></div><div class="health-copy"><div><span>知识库</span><strong>{{ stats.datasets }}</strong></div><div><span>当前工作空间</span><strong>{{ workspaceStore.currentWorkspace?.name || '未选择' }}</strong></div><p>每一份素材都可以继续被检索、引用、整理为知识卡片。</p></div></div>
          <div class="card-actions"><el-button type="primary" plain @click="router.push('/datasets/create')"><el-icon><FolderAdd /></el-icon>新建知识库</el-button><el-button plain @click="router.push('/knowledge/network')">查看知识网络</el-button></div>
        </el-card>

        <el-card shadow="never" class="dashboard-card">
          <template #header><div class="card-heading"><div><span class="section-kicker">PIPELINE</span><h2>生产动态</h2></div><el-button link @click="router.push('/runs')">运行档案 <el-icon><ArrowRight /></el-icon></el-button></div></template>
          <div class="pipeline-list"><div class="pipeline-row"><span class="pipeline-dot is-purple" :class="{ 'is-idle': !pipelineStats.research }" /><div><strong>知识与研究</strong><small>{{ pipelineStats.research ? `${pipelineStats.research} 项研究需要关注` : '暂无待处理事项' }}</small></div><el-tag size="small" effect="plain" :type="pipelineStats.research ? 'warning' : 'success'">{{ pipelineStats.research ? '待处理' : '已清空' }}</el-tag><el-button link @click="router.push('/research')">进入</el-button></div><div class="pipeline-row"><span class="pipeline-dot is-green" :class="{ 'is-idle': !pipelineStats.content }" /><div><strong>内容生产</strong><small>{{ pipelineStats.content ? `${pipelineStats.content} 项内容需要关注` : '暂无待处理事项' }}</small></div><el-tag size="small" effect="plain" :type="pipelineStats.content ? 'warning' : 'success'">{{ pipelineStats.content ? '待处理' : '已清空' }}</el-tag><el-button link @click="router.push('/content')">进入</el-button></div><div class="pipeline-row"><span class="pipeline-dot is-orange" :class="{ 'is-idle': !pipelineStats.agent }" /><div><strong>Agent 运行</strong><small>{{ pipelineStats.agent ? `${pipelineStats.agent} 项运行需要关注` : '暂无待处理事项' }}</small></div><el-tag size="small" effect="plain" :type="pipelineStats.agent ? 'warning' : 'success'">{{ pipelineStats.agent ? '待处理' : '已清空' }}</el-tag><el-button link @click="router.push('/agents')">进入</el-button></div></div>
        </el-card>
      </div>

      <el-card shadow="never" class="dashboard-card graph-card">
        <template #header><div class="card-heading"><div><span class="section-kicker">KNOWLEDGE GRAPH</span><h2>知识星图</h2></div><el-button link @click="router.push('/knowledge/network')">打开完整知识网络 <el-icon><ArrowRight /></el-icon></el-button></div></template>
        <div v-if="network.nodes.length" class="mini-graph-wrap">
          <svg viewBox="0 0 900 260" role="img" aria-label="知识星图预览">
            <defs><linearGradient id="home-graph-line" x1="0" x2="1"><stop offset="0" stop-color="#c8b5ef" /><stop offset="1" stop-color="#704ac6" /></linearGradient></defs>
            <line v-for="edge in graphEdges" :key="`home-edge-${edge.id}`" :x1="graphPosition(edge.source_item_id).x" :y1="graphPosition(edge.source_item_id).y" :x2="graphPosition(edge.target_item_id).x" :y2="graphPosition(edge.target_item_id).y" stroke="url(#home-graph-line)" stroke-width="2" stroke-opacity=".42" />
            <g v-for="node in graphNodes" :key="`home-node-${node.id}`" class="mini-graph-node">
              <circle :cx="node.x" :cy="node.y" :r="node.radius + 8" fill="#f0eaff" opacity=".82" />
              <circle :cx="node.x" :cy="node.y" :r="node.radius" fill="#704ac6" />
              <text :x="node.x" :y="node.y + node.radius + 18" text-anchor="middle">{{ node.title.slice(0, 12) }}</text>
            </g>
          </svg>
          <span class="graph-caption">{{ network.nodes.length }} 个审核通过节点 · {{ network.edges.length }} 条已确认关系</span>
        </div>
        <div v-else class="graph-empty"><div class="graph-empty-icon">✦</div><div><strong>知识星图还在等待第一张知识卡片</strong><p>审核通过知识卡片后，系统会自动把它们放进可追溯的关系网络。</p></div><el-button type="primary" plain @click="router.push('/knowledge')">去整理知识</el-button></div>
      </el-card>

      <el-card shadow="never" class="dashboard-card recent-card">
        <template #header><div class="card-heading"><div><span class="section-kicker">RECENT LIBRARIES</span><h2>最近知识库</h2></div><el-button link @click="router.push('/datasets')">查看全部 <el-icon><ArrowRight /></el-icon></el-button></div></template>
        <div v-if="recentDatasets.length" class="recent-list"><button v-for="dataset in recentDatasets" :key="dataset.id" class="recent-item" @click="router.push(`/datasets/${dataset.id}`)"><span class="recent-icon"><el-icon><FolderOpened /></el-icon></span><span class="recent-info"><strong>{{ dataset.name }}</strong><small>{{ dataset.document_count || 0 }} 个文档 · {{ formatDate(dataset.created_at) }}</small></span><el-icon class="recent-arrow"><ArrowRight /></el-icon></button></div>
        <el-empty v-else description="还没有知识库，先创建一个工作空间" :image-size="70" />
      </el-card>

    </template>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDatasetStore } from '@/stores/dataset'
import { useWorkspaceStore } from '@/stores/workspace'
import { useChatStore } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { workbenchApi } from '@/api/workbench'
import { knowledgeNetworkApi, type KnowledgeNetworkEdge, type KnowledgeNetworkNode } from '@/api/knowledge'
import { ChatDotRound, FolderOpened, Document, Setting, ChatLineSquare, ArrowRight, FolderAdd, OfficeBuilding, Upload } from '@element-plus/icons-vue'
import { formatDate } from '@/utils/format'

const router = useRouter()
const datasetStore = useDatasetStore()
const workspaceStore = useWorkspaceStore()
const chatStore = useChatStore()
const authStore = useAuthStore()
const stats = ref({ datasets: 0, documents: 0, workspaces: 0, chats: 0 })
const recentDatasets = ref<any[]>([])
const pipelineStats = ref({ research: 0, content: 0, agent: 0 })
const network = ref<{ nodes: KnowledgeNetworkNode[]; edges: KnowledgeNetworkEdge[] }>({ nodes: [], edges: [] })
const graphNodes = computed(() => {
  const visibleNodes = network.value.nodes.slice(0, 12)
  const center = { x: 450, y: 112 }
  if (visibleNodes.length === 1) return [{ ...visibleNodes[0], x: center.x, y: center.y, radius: 24 }]
  return visibleNodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(visibleNodes.length, 1) - Math.PI / 2
    const degree = network.value.edges.filter(edge => edge.source_item_id === node.id || edge.target_item_id === node.id).length
    return { ...node, x: center.x + Math.cos(angle) * 330, y: center.y + Math.sin(angle) * 75, radius: Math.min(22, 13 + degree * 3) }
  })
})
const graphEdges = computed(() => network.value.edges.filter(edge => graphNodes.value.some(node => node.id === edge.source_item_id) && graphNodes.value.some(node => node.id === edge.target_item_id)).slice(0, 24))
function graphPosition(id: string) { return graphNodes.value.find(node => node.id === id) || { x: 450, y: 112 } }

onMounted(async () => {
  if (authStore.isSuperuser) return
  try {
    await datasetStore.fetchDatasets({ page: 1, page_size: 1000, silent: true })
    stats.value.datasets = datasetStore.total
    stats.value.documents = datasetStore.datasets.reduce((sum: number, item: any) => sum + (item.document_count || 0), 0)
    recentDatasets.value = datasetStore.datasets.slice(0, 5)
  } catch (error) { console.error('Failed to fetch datasets:', error) }
  try {
    await workspaceStore.fetchWorkspaces({ page: 1, page_size: 1000 })
    stats.value.workspaces = workspaceStore.workspaces.length
  } catch (error) { console.error('Failed to fetch workspaces:', error) }
  try {
    const workspaceId = workspaceStore.currentWorkspaceId
    if (workspaceId) {
      const taskResult = await workbenchApi.listTasks(workspaceId, 100)
      const tasks = taskResult.items || []
      pipelineStats.value = {
        research: tasks.filter(task => task.kind === 'research_run').length,
        content: tasks.filter(task => ['content_review', 'content_publish'].includes(task.kind)).length,
        agent: tasks.filter(task => ['agent_approval', 'agent_run'].includes(task.kind)).length
      }
    }
  } catch (error) { console.error('Failed to fetch workbench tasks:', error) }
  try {
    const workspaceId = workspaceStore.currentWorkspaceId
    if (workspaceId) network.value = await knowledgeNetworkApi.network(workspaceId)
  } catch (error) { console.error('Failed to fetch knowledge network:', error) }
  try {
    await chatStore.fetchConversations(undefined, { silent: true })
    stats.value.chats = chatStore.conversations.length
  } catch (error) { console.error('Failed to fetch conversations:', error) }
})
</script>

<style scoped lang="scss">
.home-view { max-width: 1480px; margin: 0 auto; color: #2b2138; }
.eyebrow,.section-kicker { margin: 0; color: #8062bd; font-size: 11px; font-weight: 800; letter-spacing: .17em; text-transform: uppercase; }
.dashboard-hero,.admin-shell { display:flex; justify-content:space-between; align-items:flex-end; gap:24px; padding:10px 0 18px; }
h1 { margin:9px 0 0; color:#21172f; font-family:Georgia,'Times New Roman',serif; font-size:clamp(34px,4vw,52px); font-weight:700; letter-spacing:-.055em; }
.hero-copy,.admin-shell>p:not(.eyebrow) { max-width:650px; margin:12px 0 0; color:#81778f; font-size:15px; line-height:1.7; }
.hero-actions { display:flex; gap:10px; }.status-strip { display:flex; align-items:center; gap:18px; margin:0 0 18px; padding:11px 15px; color:#898096; font-size:12px; border:1px solid rgba(112,74,198,.11); border-radius:12px; background:rgba(255,255,255,.55); }.status-strip span:first-child { display:flex; align-items:center; gap:7px; color:#5f5470; font-weight:600; }.status-dot { width:7px; height:7px; border-radius:50%; background:#55a777; box-shadow:0 0 0 4px rgba(85,167,119,.12); }.status-strip .el-button { margin-left:auto; }
.metric-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin-bottom:18px; }.metric-card { position:relative; min-height:126px; padding:18px 20px; text-align:left; cursor:pointer; border:1px solid rgba(112,74,198,.13); border-radius:18px; background:linear-gradient(145deg,rgba(255,255,255,.96),rgba(250,247,255,.82)); box-shadow:0 10px 25px rgba(79,51,133,.045); transition:.2s ease; }.metric-card:hover { transform:translateY(-2px); border-color:#c9b2ed; box-shadow:0 16px 32px rgba(79,51,133,.1); }.metric-card span,.metric-card small { display:block; color:#8b8296; }.metric-card strong { display:block; margin:8px 0 5px; color:#2e2240; font-family:Georgia,'Times New Roman',serif; font-size:34px; letter-spacing:-.05em; }.metric-card small { font-size:11px; }.metric-card .el-icon { position:absolute; top:18px; right:18px; color:#8e6acc; font-size:20px; }.metric-card.is-accent { background:linear-gradient(145deg,#7440df,#8f5de9); border-color:#7440df; }.metric-card.is-accent span,.metric-card.is-accent small,.metric-card.is-accent strong,.metric-card.is-accent .el-icon { color:#fff; }
.dashboard-grid { display:grid; grid-template-columns:1.12fr .88fr; gap:18px; }.dashboard-card { border:1px solid rgba(112,74,198,.12); border-radius:19px; background:rgba(255,255,255,.75); box-shadow:0 10px 26px rgba(79,51,133,.04); }.dashboard-card :deep(.el-card__header) { padding:18px 20px 14px; border-bottom:1px solid rgba(112,74,198,.08); }.dashboard-card :deep(.el-card__body) { padding:20px; }.card-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }.card-heading h2 { margin:5px 0 0; font-size:20px; letter-spacing:-.03em; }.health-visual { display:flex; align-items:center; gap:26px; min-height:145px; }.health-ring { display:flex; flex:0 0 138px; flex-direction:column; align-items:center; justify-content:center; height:138px; border:10px solid #efe7ff; border-top-color:#7c50d5; border-right-color:#a783ec; border-radius:50%; background:#fff; }.health-ring strong { color:#5632a0; font-size:18px; }.health-ring span { margin-top:5px; color:#978ea3; font-size:11px; }.health-copy { flex:1; }.health-copy>div { display:flex; justify-content:space-between; gap:20px; padding:9px 0; border-bottom:1px solid #f0edf5; }.health-copy span { color:#93899c; font-size:12px; }.health-copy strong { max-width:170px; overflow:hidden; color:#43364f; font-size:13px; text-overflow:ellipsis; white-space:nowrap; }.health-copy p { margin:12px 0 0; color:#928899; font-size:12px; line-height:1.6; }.card-actions { display:flex; gap:10px; margin-top:14px; padding-top:14px; border-top:1px solid rgba(112,74,198,.08); }
.pipeline-list { display:grid; gap:2px; }.pipeline-row { display:flex; align-items:center; gap:10px; min-height:67px; border-bottom:1px solid #f0edf5; }.pipeline-row:last-child { border-bottom:0; }.pipeline-row>div { flex:1; min-width:0; }.pipeline-row strong,.pipeline-row small { display:block; }.pipeline-row strong { color:#43364f; font-size:14px; }.pipeline-row small { margin-top:5px; overflow:hidden; color:#978e9e; font-size:12px; text-overflow:ellipsis; white-space:nowrap; }.pipeline-dot { width:10px; height:10px; flex:0 0 10px; border-radius:50%; box-shadow:0 0 0 5px rgba(112,74,198,.08); }.pipeline-dot.is-purple { background:#8156db; }.pipeline-dot.is-green { background:#5ba67d; box-shadow:0 0 0 5px rgba(91,166,125,.1); }.pipeline-dot.is-orange { background:#d29b4a; box-shadow:0 0 0 5px rgba(210,155,74,.1); }.pipeline-dot.is-idle { background:#c6bfce; box-shadow:0 0 0 5px rgba(198,191,206,.12); }
.graph-card { grid-column:1 / -1; margin-top:18px; }.mini-graph-wrap { position:relative; overflow:hidden; min-height:220px; border:1px solid rgba(112,74,198,.1); border-radius:16px; background:radial-gradient(circle at 50% 45%,rgba(240,234,255,.95),rgba(255,255,255,.88) 60%,rgba(249,247,255,.65)); }.mini-graph-wrap svg { display:block; width:100%; min-height:220px; }.mini-graph-node text { fill:#514765; font-size:11px; font-weight:600; }.graph-caption { position:absolute; right:14px; bottom:10px; color:#988ea4; font-size:11px; }.graph-empty { display:flex; align-items:center; gap:15px; min-height:125px; padding:15px 18px; border:1px dashed rgba(112,74,198,.22); border-radius:15px; background:#fbfaff; }.graph-empty-icon { display:grid; width:44px; height:44px; flex:0 0 44px; place-items:center; color:#fff; font-size:21px; border-radius:14px; background:linear-gradient(135deg,#8e61df,#6330c5); }.graph-empty>div:nth-child(2) { flex:1; }.graph-empty strong { color:#43364f; font-size:14px; }.graph-empty p { margin:6px 0 0; color:#978e9e; font-size:12px; line-height:1.6; }.recent-card { margin-top:18px; }.recent-list { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px 22px; }.recent-item { display:flex; align-items:center; gap:12px; min-width:0; padding:11px 7px; text-align:left; cursor:pointer; border:0; border-bottom:1px solid #f0edf5; background:transparent; }.recent-item:hover { background:#faf7ff; }.recent-icon { display:grid; width:35px; height:35px; place-items:center; flex:0 0 35px; color:#7951c2; border-radius:10px; background:#f0e8ff; }.recent-info { min-width:0; flex:1; }.recent-info strong,.recent-info small { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }.recent-info strong { color:#43364f; font-size:13px; }.recent-info small { margin-top:4px; color:#98909e; font-size:11px; }.recent-arrow { color:#b3a8bb; }
.quick-row { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-top:18px; }.quick-row>button { display:flex; align-items:center; gap:11px; min-height:66px; padding:13px 15px; text-align:left; cursor:pointer; border:1px solid rgba(112,74,198,.1); border-radius:15px; background:#faf8fd; color:#6e5a8b; transition:.2s ease; }.quick-row>button:hover { border-color:#c9b2ed; background:#f5efff; transform:translateY(-2px); }.quick-row>button .el-icon:last-child { margin-left:auto; color:#ae9aca; }.quick-row span { flex:1; }.quick-row strong,.quick-row small { display:block; }.quick-row strong { color:#43364f; font-size:13px; }.quick-row small { margin-top:4px; color:#978e9e; font-size:11px; }
.admin-shell { min-height:430px; flex-direction:column; align-items:flex-start; justify-content:center; padding-left:clamp(10px,6vw,90px); border:1px solid rgba(112,74,198,.12); border-radius:24px; background:radial-gradient(circle at 78% 32%,rgba(147,107,229,.22),transparent 25%),linear-gradient(135deg,#fbf8ff,#f1eaff); }.admin-shell .el-button { margin-top:22px; }
@media(max-width:1000px){.metric-grid{grid-template-columns:repeat(2,1fr)}.dashboard-grid{grid-template-columns:1fr}.graph-card{grid-column:auto}}@media(max-width:700px){.dashboard-hero{display:block}.hero-actions{margin-top:18px}.status-strip{flex-wrap:wrap}.status-strip .el-button{margin-left:0}.health-visual{align-items:flex-start;flex-direction:column}.recent-list,.quick-row{grid-template-columns:1fr}.graph-empty{align-items:flex-start;flex-direction:column}}@media(max-width:480px){.metric-grid{grid-template-columns:1fr}.hero-actions{flex-direction:column}.hero-actions .el-button{width:100%}}
</style>
