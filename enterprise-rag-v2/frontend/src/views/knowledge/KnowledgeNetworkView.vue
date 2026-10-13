<template>
  <section class="network-view">
    <header class="page-header">
      <div><p class="eyebrow">AI 工作台 / 知识中心</p><h1>知识关系网络</h1><p class="subtitle">只展示审核通过的知识卡片及其显式关系，关系可追溯、可删除。</p></div>
      <div class="header-actions"><el-button @click="load" :loading="loading">刷新</el-button><el-button type="primary" plain @click="loadModelSuggestions" :loading="modelLoading">模型辅助建议</el-button></div>
    </header>
    <el-alert v-if="!workspaceId" type="warning" :closable="false">请先选择工作空间。</el-alert>
    <div class="summary"><el-tag>节点 {{ network.nodes.length }}</el-tag><el-tag type="success">关系 {{ network.edges.length }}</el-tag></div>
    <el-card shadow="never" class="network-card">
      <el-empty v-if="!network.nodes.length" description="暂无审核通过的知识卡片" />
      <div v-else>
        <div class="graph-heading"><div><span class="section-kicker">KNOWLEDGE GRAPH</span><h2>知识关系总览</h2></div><span>点击节点可在下方明细中核对关系</span></div>
        <div class="graph-canvas">
          <svg viewBox="0 0 900 420" role="img" aria-label="知识关系图">
            <defs><linearGradient id="graph-line" x1="0" x2="1"><stop offset="0" stop-color="#b79ae8" /><stop offset="1" stop-color="#704ac6" /></linearGradient></defs>
            <line v-for="edge in network.edges" :key="`line-${edge.id}`" :x1="graphPosition(edge.source_item_id).x" :y1="graphPosition(edge.source_item_id).y" :x2="graphPosition(edge.target_item_id).x" :y2="graphPosition(edge.target_item_id).y" stroke="url(#graph-line)" stroke-width="2" stroke-opacity=".45" />
            <g v-for="node in graphNodes" :key="`graph-${node.id}`" class="graph-node" :class="{ 'is-selected': selectedNodeId === node.id }" @click="selectNode(node.id)">
              <circle :cx="node.x" :cy="node.y" :r="node.radius + 9" fill="#f0eaff" opacity=".75" />
              <circle :cx="node.x" :cy="node.y" :r="node.radius" fill="#704ac6" />
              <text :x="node.x" :y="node.y + node.radius + 22" text-anchor="middle">{{ node.title.slice(0, 14) }}</text>
            </g>
          </svg>
        </div>
        <div class="detail-heading"><span class="section-kicker">RELATION DETAILS</span><span>{{ selectedNodeId ? `当前选中：${selectedNodeTitle}` : '点击图中节点查看对应关系' }}</span></div>
        <div class="node-grid">
        <div v-for="node in network.nodes" :key="node.id" class="node-card">
          <div class="node-heading"><el-icon><Share /></el-icon><strong>{{ node.title }}</strong></div>
          <span>{{ node.item_type }} · 置信度 {{ Math.round(node.confidence * 100) }}%</span>
          <div class="node-links">
            <div v-for="edge in nodeEdges(node.id)" :key="edge.id" class="edge-row">
              <span>{{ edge.source_item_id === node.id ? '→' : '←' }} {{ edge.source_item_id === node.id ? edge.target_title : edge.source_title }}</span>
              <el-tag size="small">{{ edge.relation_type }}</el-tag>
              <el-button text type="danger" size="small" @click="remove(edge.id)">删除</el-button>
            </div>
            <small v-if="!nodeEdges(node.id).length">暂无关系</small>
          </div>
        </div>
        </div>
      </div>
    </el-card>
    <el-card v-if="suggestions.length" shadow="never" class="suggestion-card">
      <template #header><div class="suggestion-header"><span>候选关系（需人工确认）</span><el-button size="small" type="primary" :disabled="!selectedSuggestionKeys.length" :loading="batchSaving" @click="acceptSelected">批量确认 {{ selectedSuggestionKeys.length ? `(${selectedSuggestionKeys.length})` : '' }}</el-button></div></template>
      <el-checkbox-group v-model="selectedSuggestionKeys">
      <div v-for="suggestion in suggestions" :key="`${suggestion.source_item_id}-${suggestion.target_item_id}`" class="suggestion-row">
        <el-checkbox :label="suggestionKey(suggestion)" />
        <span>{{ suggestion.source_title }} → {{ suggestion.target_title }}</span>
        <el-tag size="small" type="info">{{ suggestion.origin === 'model' ? '模型' : '规则' }}</el-tag>
        <el-tag size="small">{{ suggestion.matched_terms.slice(0, 3).join('、') }}</el-tag>
        <small>匹配度 {{ Math.round(suggestion.score * 100) }}%</small>
        <el-button size="small" type="primary" @click="acceptSuggestion(suggestion)">确认关系</el-button>
      </div>
      </el-checkbox-group>
    </el-card>
    <el-card shadow="never" class="create-card">
      <template #header><span>建立关系</span></template>
      <el-form inline :model="form">
        <el-form-item label="起点"><el-select v-model="form.source_item_id" placeholder="选择节点" filterable><el-option v-for="node in network.nodes" :key="node.id" :label="node.title" :value="node.id" /></el-select></el-form-item>
        <el-form-item label="关系"><el-input v-model="form.relation_type" placeholder="例如 supports" /></el-form-item>
        <el-form-item label="终点"><el-select v-model="form.target_item_id" placeholder="选择节点" filterable><el-option v-for="node in network.nodes" :key="node.id" :label="node.title" :value="node.id" /></el-select></el-form-item>
        <el-form-item><el-button type="primary" :loading="saving" @click="create">建立关系</el-button></el-form-item>
      </el-form>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Share } from '@element-plus/icons-vue'
import { knowledgeNetworkApi, type KnowledgeNetworkEdge, type KnowledgeRelationSuggestion } from '@/api/knowledge'
import { useWorkspaceStore } from '@/stores/workspace'

const workspaceStore = useWorkspaceStore()
const workspaceId = computed(() => workspaceStore.currentWorkspaceId)
const loading = ref(false)
const saving = ref(false)
const modelLoading = ref(false)
const batchSaving = ref(false)
const suggestions = ref<KnowledgeRelationSuggestion[]>([])
const selectedSuggestionKeys = ref<string[]>([])
const selectedNodeId = ref('')
const network = ref<{ nodes: { id: string; title: string; item_type: string; confidence: number }[]; edges: KnowledgeNetworkEdge[] }>({ nodes: [], edges: [] })
const form = reactive({ source_item_id: '', target_item_id: '', relation_type: '' })
const graphNodes = computed(() => {
  const nodes = network.value.nodes
  const center = { x: 450, y: 190 }
  if (nodes.length === 1) return [{ ...nodes[0], x: center.x, y: center.y, radius: 24 }]
  return nodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(nodes.length, 1) - Math.PI / 2
    const radius = Math.min(24, 13 + nodeEdges(node.id).length * 3)
    return { ...node, x: center.x + Math.cos(angle) * 285, y: center.y + Math.sin(angle) * 135, radius }
  })
})
function graphPosition(id: string) { return graphNodes.value.find(node => node.id === id) || { x: 450, y: 190 } }
function nodeEdges(id: string) { return network.value.edges.filter(edge => edge.source_item_id === id || edge.target_item_id === id) }
const selectedNodeTitle = computed(() => network.value.nodes.find(node => node.id === selectedNodeId.value)?.title || '')
function selectNode(id: string) { selectedNodeId.value = selectedNodeId.value === id ? '' : id }
async function load() {
  if (!workspaceId.value) return
  loading.value = true
  try {
    [network.value, suggestions.value] = await Promise.all([knowledgeNetworkApi.network(workspaceId.value), knowledgeNetworkApi.suggestions(workspaceId.value)])
    selectedSuggestionKeys.value = []
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '知识关系网络加载失败')
  } finally {
    loading.value = false
  }
}
async function loadModelSuggestions() {
  if (!workspaceId.value) return
  modelLoading.value = true
  try {
    suggestions.value = await knowledgeNetworkApi.modelSuggestions(workspaceId.value)
    ElMessage.success('模型候选建议已生成，请逐条人工确认')
  } catch (error) {
    ElMessage.warning(error instanceof Error ? error.message : '模型建议暂时不可用，请稍后重试')
  } finally {
    modelLoading.value = false
  }
}
async function create() {
  if (!workspaceId.value || !form.source_item_id || !form.target_item_id || !form.relation_type.trim()) return ElMessage.warning('请选择两个节点并填写关系类型')
  saving.value = true
  try { await knowledgeNetworkApi.create(workspaceId.value, { ...form, relation_type: form.relation_type.trim() }); ElMessage.success('关系已建立'); Object.assign(form, { source_item_id: '', target_item_id: '', relation_type: '' }); await load() } catch (error) { ElMessage.error(error instanceof Error ? error.message : '关系建立失败') } finally { saving.value = false }
}
async function remove(id: string) { if (!workspaceId.value) return; try { await knowledgeNetworkApi.remove(workspaceId.value, id); ElMessage.success('关系已删除'); await load() } catch (error) { ElMessage.error(error instanceof Error ? error.message : '关系删除失败') } }
async function acceptSuggestion(suggestion: KnowledgeRelationSuggestion) { if (!workspaceId.value) return; try { await knowledgeNetworkApi.create(workspaceId.value, { source_item_id: suggestion.source_item_id, target_item_id: suggestion.target_item_id, relation_type: suggestion.relation_type }); ElMessage.success('候选关系已确认'); await load() } catch (error) { ElMessage.error(error instanceof Error ? error.message : '候选关系确认失败') } }
function suggestionKey(suggestion: KnowledgeRelationSuggestion) { return `${suggestion.source_item_id}:${suggestion.target_item_id}:${suggestion.relation_type}` }
async function acceptSelected() {
  if (!workspaceId.value || !selectedSuggestionKeys.value.length) return
  const selected = suggestions.value.filter(item => selectedSuggestionKeys.value.includes(suggestionKey(item)))
  batchSaving.value = true
  try {
    await knowledgeNetworkApi.batchReview(workspaceId.value, selected.map(item => ({ source_item_id: item.source_item_id, target_item_id: item.target_item_id, relation_type: item.relation_type, description: item.description })))
    ElMessage.success(`已确认 ${selected.length} 条候选关系`)
    await load()
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '批量确认失败') } finally { batchSaving.value = false }
}
onMounted(async () => { await workspaceStore.fetchCurrentWorkspace(); await load() })
</script>

<style scoped lang="scss">
.network-view { max-width: 1440px; margin: 0 auto; }.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }.eyebrow { margin: 0 0 8px; color: var(--el-color-primary); font-weight: 600; }h1 { margin: 0; }.subtitle { color: var(--el-text-color-secondary); }.summary { display: flex; gap: 10px; margin: 20px 0; }.network-card { min-height: 280px; }.node-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }.node-card { padding: 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 10px; }.node-heading { display: flex; align-items: center; gap: 8px; font-size: 16px; }.node-card > span, .node-links small { color: var(--el-text-color-secondary); font-size: 12px; }.node-links { display: grid; gap: 8px; margin-top: 16px; }.edge-row, .suggestion-row { display: flex; align-items: center; gap: 8px; font-size: 13px; }.edge-row span, .suggestion-row span { flex: 1; }.suggestion-card, .create-card { margin-top: 16px; }.suggestion-row { padding: 8px 0; border-bottom: 1px solid var(--el-border-color-lighter); }.suggestion-row small { color: var(--el-text-color-secondary); }.el-select { width: 180px; }@media (max-width: 900px) { .node-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }@media (max-width: 600px) { .node-grid { grid-template-columns: 1fr; }.page-header { display: block; } }
 .network-view { max-width: 1440px; margin: 0 auto; }
.network-card, .suggestion-card, .create-card { border: 1px solid rgba(112,74,198,.13); border-radius: 18px; background: linear-gradient(145deg,rgba(255,255,255,.97),rgba(249,247,255,.9)); box-shadow: 0 12px 30px rgba(79,51,133,.05); }
.graph-heading, .detail-heading { display:flex; justify-content:space-between; align-items:flex-end; gap:12px; }
.graph-heading h2 { margin: 5px 0 0; font-size: 20px; }
.graph-heading > span, .detail-heading > span:last-child { color: var(--el-text-color-secondary); font-size: 12px; }
.graph-canvas { min-height: 420px; margin: 18px 0; overflow:hidden; border:1px solid rgba(112,74,198,.1); border-radius:16px; background: radial-gradient(circle at 50% 45%, rgba(240,234,255,.95), rgba(255,255,255,.88) 58%, rgba(249,247,255,.65)); }
.graph-canvas svg { display:block; width:100%; height:auto; min-height:420px; }
.graph-node { cursor:pointer; transition: opacity .2s; }
.graph-node:hover { opacity:.78; }
.graph-node.is-selected circle:last-of-type { stroke:#f6f0ff; stroke-width:5; }
.graph-node.is-selected text { fill:#4c3284; font-weight:800; }
.graph-node text { fill:#514765; font-size:12px; font-weight:600; }
.detail-heading { padding: 6px 0 12px; border-bottom:1px solid rgba(112,74,198,.1); }
.node-card { border-color: rgba(112,74,198,.12); border-radius:14px; background: rgba(255,255,255,.7); }
.suggestion-header { display:flex; align-items:center; justify-content:space-between; gap:12px; }.suggestion-row { padding: 10px 0; }
@media (max-width: 700px) { .graph-heading, .detail-heading { align-items:flex-start; flex-direction:column; } .graph-canvas { min-height:300px; } .graph-canvas svg { min-height:300px; } }
</style>
