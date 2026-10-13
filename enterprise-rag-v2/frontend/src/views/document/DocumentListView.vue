<template>
  <div
    class="document-list-view"
    :class="{ 'document-list-view--embed': embed }"
  >
    <div
      v-if="!embed"
      class="header"
    >
      <div class="header-left">
        <el-button
          text
          @click="router.push(`/datasets/${datasetId}`)"
        >
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <h1>文档管理</h1>
      </div>
      <div class="header-right">
        <el-button
          v-if="canUploadDocument"
          type="primary"
          @click="router.push(`/datasets/${datasetId}/documents/upload`)"
        >
          <el-icon><Upload /></el-icon>
          上传文档
        </el-button>
      </div>
    </div>

    <div
      v-else
      class="embed-toolbar"
    >
      <h2 class="embed-title">
        文档列表
      </h2>
      <el-button
        v-if="canUploadDocument"
        type="primary"
        @click="router.push(`/datasets/${datasetId}/documents/upload`)"
      >
        <el-icon><Upload /></el-icon>
        上传文档
      </el-button>
    </div>

    <el-card class="filter-card">
      <el-form inline>
        <el-form-item label="搜索">
          <el-input
            v-model="filterKeyword"
            clearable
            placeholder="搜索文档名称"
            @keyup.enter="handleFilter"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="filterStatus"
            placeholder="全部状态"
            clearable
          >
            <el-option
              label="待处理"
              value="pending"
            />
            <el-option
              label="处理中"
              value="processing"
            />
            <el-option
              label="已完成"
              value="completed"
            />
            <el-option
              label="失败"
              value="failed"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button @click="handleFilter">
            筛选
          </el-button>
          <el-button @click="handleReset">
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-alert
      v-if="processingCount > 0"
      class="processing-alert"
      :title="`正在处理 ${processingCount} 个文档（队列中 ${pendingCount}，处理中 ${activeProcessingCount}）`"
      type="info"
      :closable="false"
      show-icon
    />

    <el-card
      v-if="loading"
      class="loading"
    >
      <LoadingSpinner text="加载中..." />
    </el-card>

    <el-card
      v-else-if="documents.length === 0"
      class="empty"
    >
      <el-empty description="暂无文档">
        <el-button
          v-if="canUploadDocument"
          type="primary"
          @click="router.push(`/datasets/${datasetId}/documents/upload`)"
        >
          上传文档
        </el-button>
      </el-empty>
    </el-card>

    <el-card v-else>
      <el-table
        :data="documents"
        row-key="id"
        style="width: 100%"
      >
        <el-table-column
          prop="name"
          label="文件名"
          min-width="200"
        >
          <template #default="{ row }">
            <div class="file-name">
              <el-icon :size="20">
                <Document />
              </el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          prop="type"
          label="类型"
          width="100"
        />
        <el-table-column
          prop="size"
          label="大小"
          width="120"
        >
          <template #default="{ row }">
            {{ formatFileSize(row.size) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="status"
          label="状态"
          min-width="200"
        >
          <template #default="{ row }">
            <div class="status-cell">
              <el-tag :type="getStatusType(row.status)">
                {{ getStatusLabel(row.status) }}
              </el-tag>
              <p
                v-if="row.status === 'failed' && getFailureUserMessage(row)"
                class="status-failure-hint"
              >
                {{ getFailureUserMessage(row) }}
              </p>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          prop="progress"
          label="进度"
          width="170"
        >
          <template #default="{ row }">
            <el-progress
              v-if="shouldShowProgress(row.status)"
              :percentage="Math.max(1, Number(row.progress || 0))"
              :stroke-width="8"
              :indeterminate="row.status === 'pending' && Number(row.progress || 0) <= 1"
            />
            <div
              v-if="shouldShowProgress(row.status)"
              class="progress-phase"
            >
              {{ getProgressText(row) }}
            </div>
            <span v-else-if="row.status === 'completed'">-</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="segment_count"
          label="分段数"
          width="100"
        />
        <el-table-column
          prop="created_at"
          label="上传时间"
          width="180"
        >
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          label="操作"
          width="220"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :loading="fullTextLoadingId === row.id"
              :disabled="row.status !== 'completed'"
              @click="handleViewFullText(row)"
            >
              查看原文
            </el-button>
            <el-button
              link
              type="primary"
              :disabled="row.status !== 'completed'"
              @click="router.push(`/documents/${row.id}/read` )"
            >
              阅读台
            </el-button>
            <el-button
              link
              type="primary"
              @click="handleViewSegments(row)"
            >
              分段
            </el-button>
            <el-button
              v-if="canDeleteDocument"
              link
              type="danger"
              @click="handleDelete(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div
        v-if="total > pageSize"
        class="pagination"
      >
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="showFullTextDialog"
      title="文档原文"
      width="920px"
      destroy-on-close
    >
      <el-scrollbar max-height="620px">
        <pre class="full-text-body">{{ fullTextContent || '（无文本内容）' }}</pre>
      </el-scrollbar>
    </el-dialog>

    <el-dialog
      v-model="showSegmentsDialog"
      title="文档分段"
      width="800px"
    >
      <el-table
        :data="segments"
        max-height="400"
      >
        <el-table-column
          label="序号"
          width="80"
        >
          <template #default="{ row, $index }">
            {{ (segmentCurrentPage - 1) * segmentPageSize + $index + 1 }}
          </template>
        </el-table-column>
        <el-table-column
          prop="content"
          label="内容"
          min-width="400"
          show-overflow-tooltip
        />
        <el-table-column
          label="字数"
          width="100"
        >
          <template #default="{ row }">
            {{ row.content?.length || 0 }}
          </template>
        </el-table-column>
      </el-table>
      <div
        v-if="segmentTotal > segmentPageSize"
        class="pagination"
      >
        <el-pagination
          v-model:current-page="segmentCurrentPage"
          :page-size="segmentPageSize"
          :total="segmentTotal"
          layout="prev, pager, next"
          @current-change="handleSegmentPageChange"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDatasetStore } from '@/stores/dataset'
import {
  getDocuments,
  deleteDocument,
  getDocumentSegments,
  getDocumentFullText,
  isValidDatasetIdForApi
} from '@/api/document'
import { ArrowLeft, Upload, Document } from '@element-plus/icons-vue'
import { formatDateTime, formatFileSize } from '@/utils/format'
import { usePermission } from '@/composables/usePermission'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { Document as DocType, Segment } from '@/types'

const props = withDefaults(defineProps<{ embed?: boolean }>(), { embed: false })

const route = useRoute()
const router = useRouter()
const datasetStore = useDatasetStore()
const { canUploadDocument, canDeleteDocument } = usePermission()

const datasetId = computed(() => {
  const raw = route.params.id
  if (Array.isArray(raw)) return String(raw[0] ?? '')
  return String(raw ?? '')
})
const documents = ref<DocType[]>([])
const segments = ref<Segment[]>([])
const total = ref(0)
const pageSize = ref(20)
const currentPage = ref(1)
const filterKeyword = ref('')
const filterStatus = ref<string | undefined>(undefined)
const showFullTextDialog = ref(false)
const fullTextContent = ref('')
const fullTextLoadingId = ref<string | null>(null)
const showSegmentsDialog = ref(false)
const segmentTotal = ref(0)
const segmentPageSize = ref(20)
const segmentCurrentPage = ref(1)
const currentDocId = ref('')
const loading = ref(false)
const POLL_INTERVAL_MS = 1500
let pollTimer: number | null = null

const statusMap: Record<string, { label: string; type: string }> = {
  pending: { label: '队列中', type: 'info' },
  processing: { label: '处理中', type: 'warning' },
  completed: { label: '已完成', type: 'success' },
  failed: { label: '失败', type: 'danger' }
}

const getStatusLabel = (status: string) => statusMap[status]?.label || status
const getStatusType = (status: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' =>
  (statusMap[status]?.type as 'primary' | 'success' | 'warning' | 'info' | 'danger') || 'info'
const phaseMap: Record<string, string> = {
  extracting: '提取文本',
  chunking: '切分文本',
  embedding: '向量计算',
  indexing: '写入索引',
  completed: '处理完成',
  failed: '处理失败'
}
const getProcessingPhaseLabel = (phase?: string) => phaseMap[String(phase || '')] || '处理中'
const shouldShowProgress = (status: string) => ['pending', 'processing'].includes(String(status).toLowerCase())
const getProgressText = (doc: DocType) => {
  const done = Number(doc.done_chunks || 0)
  const total = Number(doc.total_chunks || 0)
  if (total > 0) return `${done}/${total} 段`
  if (String(doc.status).toLowerCase() === 'pending') return '排队中'
  return getProcessingPhaseLabel(doc.processing_phase)
}

/** 将后端 error_reason 转为用户可读说明（不暴露服务器路径等细节） */
const getFailureUserMessage = (doc: DocType): string => {
  const raw = String(doc.error_reason || '').trim()
  if (!raw) {
    return '处理未成功。可删除该文档后重新上传再试。'
  }
  if (raw.includes('源文件不存在')) {
    return '原始文件在服务器上已找不到（例如部署或清理导致丢失）。请删除本条记录后重新上传同一文件。'
  }
  if (raw.includes('无法从文档') && raw.includes('提取文本')) {
    return '无法从该文件中解析出可用文本，请确认文件未损坏，或换用其他格式后重新上传。'
  }
  const short = raw.length > 120 ? `${raw.slice(0, 120)}…` : raw
  return `处理失败：${short}`
}
const pendingCount = computed(() =>
  documents.value.filter((doc) => String(doc.status).toLowerCase() === 'pending').length
)
const activeProcessingCount = computed(() =>
  documents.value.filter((doc) => String(doc.status).toLowerCase() === 'processing').length
)
const processingCount = computed(() => pendingCount.value + activeProcessingCount.value)

const fetchDocuments = async (options: { silent?: boolean } = {}) => {
  if (!isValidDatasetIdForApi(datasetId.value)) {
    stopPolling()
    documents.value = []
    total.value = 0
    return
  }
  if (!options.silent) {
    loading.value = true
  }
  try {
    const res = await getDocuments(datasetId.value, {
      page: currentPage.value,
      page_size: pageSize.value,
      status: filterStatus.value,
      keyword: filterKeyword.value.trim() || undefined
    })
    const result = res as any
    documents.value = result.data?.items || result.items || []
    total.value = result.data?.total || result.total || 0
    syncPolling()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : ''
    if (msg === 'INVALID_DATASET_ID') {
      stopPolling()
      documents.value = []
      total.value = 0
    }
  } finally {
    if (!options.silent) {
      loading.value = false
    }
  }
}

const shouldPoll = () =>
  documents.value.some((doc) => ['pending', 'processing'].includes(String(doc.status).toLowerCase()))

const stopPolling = () => {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

const startPolling = () => {
  if (pollTimer !== null) return
  pollTimer = window.setInterval(() => {
    fetchDocuments({ silent: true })
  }, POLL_INTERVAL_MS)
}

const syncPolling = () => {
  if (shouldPoll()) {
    startPolling()
  } else {
    stopPolling()
  }
}

const fetchSegments = async () => {
  try {
    const res = await getDocumentSegments(currentDocId.value, {
      page: segmentCurrentPage.value,
      page_size: segmentPageSize.value
    })
    const result = res as any
    segments.value = result.data?.items || result.items || []
    segmentTotal.value = result.data?.total || result.total || 0
    if ((result.data?.items?.length || result.items?.length || 0) === 0 && (result.data?.total || result.total || 0) === 0) {
      ElMessage.info('文档正在处理中，请稍后再查看分段')
    }
  } catch (error: any) {
    if (error.response?.status === 404) {
      ElMessage.warning('文档不存在或正在处理中')
    } else {
      ElMessage.error('获取分段失败')
    }
  }
}

watch(
  datasetId,
  async (id) => {
    if (!isValidDatasetIdForApi(id)) {
      stopPolling()
      documents.value = []
      total.value = 0
      return
    }
    // embed 时由 DatasetDetailView 已拉取知识库；此处再 fetchDataset 会置 store.loading，
    // 父组件 v-if 卸载本组件，watch immediate 再次触发 → 请求死循环。
    if (!props.embed) {
      await datasetStore.fetchDataset(id)
    }
    currentPage.value = 1
    await fetchDocuments()
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  stopPolling()
})

const handleFilter = () => {
  currentPage.value = 1
  fetchDocuments()
}

const handleReset = () => {
  filterKeyword.value = ''
  filterStatus.value = undefined
  currentPage.value = 1
  fetchDocuments()
}

const handlePageChange = (page: number) => {
  currentPage.value = page
  fetchDocuments()
}

const handleViewFullText = async (doc: DocType) => {
  if (doc.status !== 'completed') {
    ElMessage.warning('请待文档处理完成后再查看原文')
    return
  }
  fullTextLoadingId.value = doc.id
  fullTextContent.value = ''
  try {
    const text = await getDocumentFullText(doc.id)
    fullTextContent.value = text
    showFullTextDialog.value = true
    if (!text.trim()) {
      ElMessage.info('暂无已索引文本，可先查看「分段」是否已生成')
    }
  } catch {
    ElMessage.error('加载原文失败')
  } finally {
    fullTextLoadingId.value = null
  }
}

const handleViewSegments = (doc: DocType) => {
  currentDocId.value = doc.id
  segmentCurrentPage.value = 1
  fetchSegments()
  showSegmentsDialog.value = true
}

const handleSegmentPageChange = (page: number) => {
  segmentCurrentPage.value = page
  fetchSegments()
}

const handleDelete = async (doc: DocType) => {
  await ElMessageBox.confirm('确定删除该文档吗？', '提示', { type: 'warning' })
  await deleteDocument(doc.id)
  ElMessage.success('删除成功')
  fetchDocuments()
}
</script>

<style scoped lang="scss">
.document-list-view--embed {
  .filter-card {
    margin-top: 0;
  }
}

.document-list-view {
  --card-bg: rgba(255, 255, 255, 0.9);
  --card-border: rgba(148, 163, 184, 0.2);

  .embed-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    gap: 12px;
  }

  .embed-title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--el-text-color-primary);
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;

      h1 {
        margin: 0;
        font-size: 24px;
        font-weight: 600;
        color: var(--el-text-color-primary);
      }
    }
  }

  .filter-card {
    margin-bottom: 20px;
    border-radius: 14px;
    border: 1px solid var(--card-border);
    background: var(--card-bg);
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
    backdrop-filter: blur(8px);
  }

  .processing-alert {
    margin-bottom: 20px;
    border-radius: 12px;
  }

  .loading,
  .empty {
    padding: 60px 0;
    border-radius: 14px;
    border: 1px solid var(--card-border);
    background: var(--card-bg);
  }

  :deep(.el-card) {
    border-radius: 14px;
    border-color: var(--card-border);
    background: var(--card-bg);
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
  }

  :deep(.el-table th.el-table__cell) {
    background: rgba(124, 77, 200, 0.06);
  }

  :deep(.el-table__row) {
    transition: background-color 0.2s ease;
  }

  .file-name {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .status-cell {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .status-failure-hint {
    margin: 0;
    font-size: 12px;
    line-height: 1.45;
    color: var(--el-color-danger);
    max-width: 280px;
    word-break: break-word;
  }

  .pagination {
    margin-top: 20px;
    display: flex;
    justify-content: center;
  }

  .progress-phase {
    margin-top: 4px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
    line-height: 1.2;
  }

  .full-text-body {
    margin: 0;
    padding: 16px;
    font-size: 16px;
    line-height: 1.8;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    color: #303133;
  }
}

:global(html.dark) .document-list-view {
  --card-bg: rgba(30, 41, 59, 0.72);
  --card-border: rgba(148, 163, 184, 0.2);
}
</style>
