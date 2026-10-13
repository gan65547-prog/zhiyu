<template>
  <section class="asset-center">
    <header class="page-header">
      <div>
        <p class="eyebrow">
          AI 工作台 / 素材中心
        </p>
        <h1>统一素材中心</h1>
        <p class="subtitle">
          文件、网页和后续连接器素材统一进入处理流水线。
        </p>
      </div>
      <el-button
        type="primary"
        :disabled="!workspaceId"
        @click="dialogVisible = true"
      >
        <el-icon><Plus /></el-icon> 添加素材
      </el-button>
    </header>

    <el-alert
      v-if="!workspaceId"
      type="warning"
      :closable="false"
      show-icon
    >
      请先选择或创建工作空间，再添加素材。
    </el-alert>

    <div class="stats-grid">
      <el-card
        v-for="stat in stats"
        :key="stat.label"
        shadow="never"
        class="stat-card"
      >
        <span class="stat-label">{{ stat.label }}</span>
        <strong>{{ stat.value }}</strong>
      </el-card>
    </div>

    <el-card
      shadow="never"
      class="table-card"
    >
      <template #header>
        <div class="table-header">
          <span>最近素材</span><el-button
            text
            :loading="loading"
            @click="loadAssets"
          >
            刷新
          </el-button>
        </div>
      </template>
      <el-table
        v-loading="loading"
        :data="assets"
        :row-class-name="assetRowClassName"
        empty-text="暂无素材"
      >
        <el-table-column
          prop="title"
          label="名称"
          min-width="220"
        />
        <el-table-column
          label="来源"
          width="110"
        >
          <template #default="{ row }">
            {{ sourceLabel(row.source_type) }}
          </template>
        </el-table-column>
        <el-table-column
          label="状态"
          width="130"
        >
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="进度"
          width="130"
        >
          <template #default="{ row }">
            <el-progress
              v-if="row.status === 'processing'"
              :percentage="row.progress || 0"
              :stroke-width="6"
              :show-text="false"
            />
            <span v-else>{{ row.status === 'ready' ? '100%' : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="处理说明"
          min-width="220"
        >
          <template #default="{ row }">
            <el-tooltip
              v-if="row.processing_error"
              :content="row.processing_error"
              placement="top-start"
            >
              <span class="processing-error">{{ row.processing_error }}</span>
            </el-tooltip>
            <span v-else class="action-hint">{{ processingHint(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="更新时间"
          width="190"
        >
          <template #default="{ row }">
            {{ formatDate(row.updated_at || row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          label="操作"
          width="190"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'failed' || row.stalled"
              text
              type="primary"
              :loading="retryingId === row.id"
              @click="retryAsset(row)"
            >
              {{ row.stalled ? '恢复处理' : '重试' }}
            </el-button>
            <el-button
              v-if="row.status === 'ready' && row.legacy_document_id"
              text
              type="success"
              @click="organizeAsset(row)"
            >
              提炼知识
            </el-button>
            <span
              v-else-if="row.status === 'ready'"
              class="action-hint"
            >
              绑定知识库后可提炼
            </span>
            <el-button
              text
              type="danger"
              @click="removeAsset(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-footer">
        <span>共 {{ assetTotal }} 条统一素材</span>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          background
          layout="total, sizes, prev, pager, next"
          :total="assetTotal"
          :page-sizes="[12, 24, 48]"
          @current-change="loadAssets"
          @size-change="handlePageSizeChange"
      />
    </div>

    <el-card v-if="activeBatch" shadow="never" class="batch-card">
      <div class="batch-header">
        <div><strong>最近导入批次</strong><span>{{ batchStatusLabel(activeBatch.status) }} · {{ activeBatch.completed_count }}/{{ activeBatch.total_count }} 已完成</span></div>
        <el-button v-if="activeBatch.failed_count" size="small" type="warning" :loading="batchRetrying" @click="retryBatch">重试失败项</el-button>
      </div>
      <el-progress :percentage="batchProgress" :status="activeBatch.status === 'failed' ? 'exception' : activeBatch.status === 'completed' ? 'success' : undefined" />
    </el-card>
    </el-card>

    <el-card
      v-if="legacyDocuments.length"
      shadow="never"
      class="table-card document-index-card"
    >
      <template #header>
        <div class="table-header">
          <span>知识库文档 · 已纳入统一索引</span>
          <el-button text @click="router.push('/datasets')">管理知识库</el-button>
        </div>
      </template>
      <el-table :data="legacyDocuments" empty-text="暂无已索引文档">
        <el-table-column prop="name" label="文档名称" min-width="260" />
        <el-table-column prop="datasetName" label="所属知识库" min-width="180" />
        <el-table-column label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="documentStatusType(row.status)">{{ documentStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="segment_count" label="分段" width="90" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :disabled="row.status !== 'completed'"
              @click="router.push(`/documents/${row.id}/read`)"
            >
              阅读台
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      title="添加素材"
      width="520px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="来源类型">
          <el-radio-group v-model="form.source_type">
            <el-radio-button value="file">
              文件
            </el-radio-button><el-radio-button value="url">
              网页 URL
            </el-radio-button><el-radio-button value="text">
              粘贴文本
            </el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item
          label="名称"
          required
        >
          <el-input
            v-model="form.title"
            placeholder="例如：2026 行业报告"
          />
        </el-form-item>
        <el-form-item
          v-if="form.source_type === 'url'"
          label="URL"
          required
        >
          <el-input
            v-model="form.source_uri"
            type="textarea"
            :rows="3"
            placeholder="每行一个 URL，例如：\nhttps://example.com/report\nhttps://example.com/guide"
          />
        </el-form-item>
        <el-form-item
          v-else-if="form.source_type === 'file'"
          label="文件"
          required
        >
          <el-upload
            :auto-upload="false"
            multiple
            :limit="50"
            :on-change="handleFileChange"
            :on-remove="clearFile"
          >
            <el-button>选择多个文件</el-button><template #tip>
              <div class="el-upload__tip">
                支持批量选择，单文件不超过 20MB；系统会自动绑定到默认资料库。
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item
          v-if="form.source_type === 'text'"
          label="文本内容"
          required
        >
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="8"
            maxlength="2000000"
            show-word-limit
            placeholder="粘贴需要整理、检索或研究的原文"
          />
        </el-form-item>
        <el-form-item label="目标知识库">
          <el-select
            v-model="form.dataset_id"
            clearable
            placeholder="可选：不选则自动进入默认资料库"
            class="full-width"
          >
            <el-option
              v-for="dataset in datasetStore.datasets"
              :key="dataset.id"
              :label="dataset.name"
              :value="dataset.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">
          取消
        </el-button><el-button
          type="primary"
          :loading="submitting"
          @click="submitAsset"
        >
          {{ form.source_type === 'file' ? '批量导入并处理' : '开始处理' }}
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { assetApi } from '@/api/asset'
import type { Asset, AssetBatch, AssetSourceType } from '@/types/asset'
import { getDocuments } from '@/api/document'
import type { Document } from '@/types/document'
import { useWorkspaceStore } from '@/stores/workspace'
import { useDatasetStore } from '@/stores/dataset'

const workspaceStore = useWorkspaceStore()
const datasetStore = useDatasetStore()
const router = useRouter()
const route = useRoute()
const assets = ref<Asset[]>([])
const legacyDocuments = ref<Array<Document & { datasetName: string }>>([])
const loading = ref(false)
const submitting = ref(false)
const retryingId = ref<string | null>(null)
const dialogVisible = ref(false)
const selectedFiles = ref<File[]>([])
const page = ref(1)
const pageSize = ref(12)
const assetTotal = ref(0)
const assetStatusTotals = reactive({ pending: 0, processing: 0, ready: 0, failed: 0 })
const activeBatch = ref<AssetBatch | null>(null)
const batchRetrying = ref(false)
const form = reactive<{ source_type: AssetSourceType; title: string; source_uri: string; content: string; dataset_id?: string }>({ source_type: 'file', title: '', source_uri: '', content: '', dataset_id: undefined })
const workspaceId = computed(() => workspaceStore.currentWorkspaceId)
const targetAssetId = computed(() => String(route.query.asset_id || ''))
let refreshTimer: number | undefined
const stats = computed(() => [
  { label: '全部素材', value: assetTotal.value + legacyDocuments.value.length },
  { label: '处理中', value: assetStatusTotals.pending + assetStatusTotals.processing + legacyDocuments.value.filter(item => ['pending', 'processing'].includes(item.status)).length },
  { label: '已就绪', value: assetStatusTotals.ready + legacyDocuments.value.filter(item => item.status === 'completed').length },
  { label: '失败', value: assetStatusTotals.failed + legacyDocuments.value.filter(item => item.status === 'failed').length }
])

async function loadLegacyDocuments() {
  const results = await Promise.allSettled(datasetStore.datasets.map(async (dataset) => {
    const response = await getDocuments(dataset.id, { page: 1, page_size: 100 }) as any
    const payload = response?.data || response
    return (payload?.items || []).map((document: Document) => ({
      ...document,
      datasetName: dataset.name,
    }))
  }))
  legacyDocuments.value = results.flatMap(result => result.status === 'fulfilled' ? result.value : [])
}

async function loadAssets() {
  const id = workspaceId.value
  if (!id) return
  loading.value = true
  try {
    const [pageResult, ...statusResults] = await Promise.all([
      assetApi.list(id, { page: page.value, page_size: pageSize.value }),
      ...(['pending', 'processing', 'ready', 'failed'] as const).map(status => assetApi.list(id, { page: 1, page_size: 1, status: String(status) }))
    ])
    assetTotal.value = pageResult.total ?? pageResult.items?.length ?? 0
    ;(['pending', 'processing', 'ready', 'failed'] as const).forEach((status, index) => {
      assetStatusTotals[status] = statusResults[index]?.total ?? 0
    })
    const result = pageResult.items || []
    assets.value = await Promise.all(result.map(async (asset) => {
      if (asset.status !== 'processing') return asset
      try {
        const status = await assetApi.processingStatus(asset.id)
        return { ...asset, status: status.status as Asset['status'], progress: status.progress, stalled: status.stalled, processing_error: status.processing_error }
      } catch {
        return asset
      }
    }))
    await loadLegacyDocuments()
  } finally { loading.value = false }
}
function handlePageSizeChange() { page.value = 1; loadAssets() }
function assetRowClassName({ row }: { row: Asset }) { return row.id === targetAssetId.value ? 'target-asset-row' : '' }
function handleFileChange(file: UploadFile) {
  const raw = file.raw
  if (raw && !selectedFiles.value.some(item => item.name === raw.name && item.size === raw.size)) selectedFiles.value.push(raw)
  if (selectedFiles.value.length === 1 && !form.title) form.title = selectedFiles.value[0].name
}
function clearFile(file?: UploadFile) {
  const raw = file?.raw
  if (!raw) { selectedFiles.value = []; return }
  selectedFiles.value = selectedFiles.value.filter(item => !(item.name === raw.name && item.size === raw.size))
}
async function submitAsset() {
  if (!workspaceId.value) return ElMessage.warning('请先选择工作空间')
  if (form.source_type !== 'file' && form.source_type !== 'url' && !form.title.trim()) return ElMessage.warning('请填写素材名称')
  if (form.source_type === 'url' && !form.source_uri.trim()) return ElMessage.warning('请输入 URL')
  if (form.source_type === 'file' && !selectedFiles.value.length) return ElMessage.warning('请选择至少一个文件')
  if (form.source_type === 'text' && !form.content.trim()) return ElMessage.warning('请输入文本内容')
  submitting.value = true
  try {
    if (form.source_type === 'file') {
      const batch = await assetApi.importBatch(workspaceId.value, selectedFiles.value, form.dataset_id)
      activeBatch.value = batch
      ElMessage.success(`已提交 ${batch.total_count} 个文件，${batch.failed_count ? `${batch.failed_count} 个失败` : '全部进入处理'}`)
    } else if (form.source_type === 'url') {
      const urls = [...new Set(form.source_uri.split(/\r?\n/).map(item => item.trim()).filter(Boolean))]
      if (urls.length > 50) return ElMessage.warning('一次最多导入 50 个 URL')
      if (urls.length > 1) {
        activeBatch.value = await assetApi.importUrls(workspaceId.value, urls, form.dataset_id)
        ElMessage.success(`已提交 ${urls.length} 个 URL，进入统一处理批次`)
      } else {
        const asset = await assetApi.create({ workspace_id: workspaceId.value, dataset_id: form.dataset_id, source_type: 'url', title: form.title.trim() || urls[0].slice(0, 255), source_uri: urls[0] })
        await assetApi.ingest(asset.id)
        ElMessage.success('素材已进入处理流水线')
      }
    } else {
      const asset = await assetApi.create({
        workspace_id: workspaceId.value,
        dataset_id: form.dataset_id,
        source_type: form.source_type,
        title: form.title.trim(),
        source_uri: form.source_uri.trim() || undefined
      })
      if (form.source_type === 'text') await assetApi.ingestText(asset.id, form.content)
      ElMessage.success('素材已进入处理流水线')
    }
    dialogVisible.value = false
    Object.assign(form, { source_type: 'file', title: '', source_uri: '', content: '', dataset_id: undefined })
    selectedFiles.value = []
    await loadAssets()
  } finally { submitting.value = false }
}
async function loadBatch() {
  if (!workspaceId.value || !activeBatch.value || ['completed', 'completed_with_errors', 'failed'].includes(activeBatch.value.status)) return
  activeBatch.value = await assetApi.getBatch(workspaceId.value, activeBatch.value.id)
}
async function retryBatch() {
  if (!workspaceId.value || !activeBatch.value) return
  batchRetrying.value = true
  try { activeBatch.value = await assetApi.retryBatch(workspaceId.value, activeBatch.value.id); ElMessage.success('失败项已重新提交') } finally { batchRetrying.value = false }
}
async function removeAsset(asset: Asset) { await ElMessageBox.confirm(`确认删除“${asset.title}”？`, '删除素材', { type: 'warning' }); await assetApi.remove(asset.id); ElMessage.success('素材已删除'); await loadAssets() }
async function retryAsset(asset: Asset) {
  retryingId.value = asset.id
  try {
    await assetApi.retry(asset.id)
    ElMessage.success('已重新提交处理')
    await loadAssets()
  } finally {
    retryingId.value = null
  }
}
async function organizeAsset(asset: Asset) {
  try {
    await assetApi.organize(asset.id)
    ElMessage.success('知识草稿已进入 Agent 处理')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '知识提炼失败，请稍后重试')
  }
}
function sourceLabel(source: AssetSourceType) { return ({ file: '文件', url: '网页', text: '文本', chat: '聊天' }[source] || source) }
function statusLabel(status: string) { return ({ pending: '待处理', processing: '处理中', ready: '已就绪', failed: '失败', deleted: '已删除' }[status] || status) }
function statusType(status: string) { return status === 'ready' ? 'success' : status === 'failed' ? 'danger' : status === 'processing' ? 'warning' : 'info' }
function processingHint(status: string) {
  return ({ pending: '等待处理队列消费', processing: '正在解析并写入知识索引', ready: '可继续提炼为知识', failed: '处理失败，可查看原因后重试' }[status] || '-')
}
const batchProgress = computed(() => activeBatch.value ? Math.round(((activeBatch.value.completed_count + activeBatch.value.failed_count) / Math.max(activeBatch.value.total_count, 1)) * 100) : 0)
function batchStatusLabel(status: string) { return ({ processing: '处理中', completed: '已完成', completed_with_errors: '部分完成', failed: '全部失败' }[status] || status) }
function documentStatusLabel(status: string) { return ({ pending: '待处理', processing: '处理中', completed: '已完成', failed: '失败' }[status] || status) }
function documentStatusType(status: string) { return status === 'completed' ? 'success' : status === 'failed' ? 'danger' : status === 'processing' ? 'warning' : 'info' }
function formatDate(value?: string | null) { return value ? new Date(value).toLocaleString('zh-CN') : '-' }
onMounted(async () => {
  await workspaceStore.fetchCurrentWorkspace()
  await datasetStore.fetchDatasets({ silent: true })
  await loadAssets()
  refreshTimer = window.setInterval(() => {
    if (assets.value.some(item => item.status === 'pending' || item.status === 'processing')) loadAssets()
    if (activeBatch.value?.status === 'processing') loadBatch()
  }, 5000)
})
onUnmounted(() => { if (refreshTimer) window.clearInterval(refreshTimer) })
</script>

<style scoped lang="scss">
.asset-center { max-width: 1440px; margin: 0 auto; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.eyebrow { margin: 0 0 8px; color: var(--el-color-primary); font-size: 13px; font-weight: 600; }
h1 { margin: 0; font-size: 30px; color: var(--el-text-color-primary); }
.subtitle { margin: 8px 0 0; color: var(--el-text-color-secondary); }
.stats-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 18px 0; }
.stat-card strong { display: block; margin-top: 8px; font-size: 28px; color: var(--el-text-color-primary); }
.stat-label { color: var(--el-text-color-secondary); font-size: 13px; }
.batch-card { margin-bottom: 18px; border: 1px solid rgba(112, 74, 198, .16); background: #faf8ff; }
.batch-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 10px; }
.batch-header div { display: flex; flex-direction: column; gap: 5px; }.batch-header span { color: var(--el-text-color-secondary); font-size: 12px; }
.table-card { border: 1px solid var(--el-border-color-lighter); }
:deep(.target-asset-row > td.el-table__cell) { background: #fff7e6 !important; }
.document-index-card { margin-top: 18px; }
.table-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.table-footer { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding-top: 16px; color: var(--el-text-color-secondary); font-size: 12px; }
.action-hint { color: var(--el-text-color-secondary); font-size: 12px; white-space: nowrap; }
.processing-error { display: inline-block; max-width: 280px; overflow: hidden; color: var(--el-color-danger); font-size: 12px; text-overflow: ellipsis; vertical-align: middle; white-space: nowrap; }
.full-width { width: 100%; }
@media (max-width: 760px) { .page-header { display: block; } .page-header .el-button { margin-top: 16px; } .stats-grid { grid-template-columns: repeat(2, 1fr); } .table-footer { display: block; } .table-footer .el-pagination { margin-top: 12px; justify-content: flex-start; flex-wrap: wrap; } }
</style>
