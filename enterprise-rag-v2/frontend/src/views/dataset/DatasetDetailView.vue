<template>
  <div class="dataset-detail-view">
    <div class="header">
      <div class="header-left">
        <el-button
          text
          @click="router.push('/datasets')"
        >
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <h1>{{ datasetStore.currentDataset?.name || '知识库详情' }}</h1>
      </div>
      <div class="header-right">
        <el-button
          :disabled="pageLoading || !datasetStore.currentDataset"
          @click="toggleDocuments"
        >
          <el-icon><Document /></el-icon>
          {{ showDocumentList ? '收起文档' : '查看文档' }}
        </el-button>
        <el-button
          type="primary"
          @click="router.push(`/chat/${id}`)"
        >
          <el-icon><ChatDotRound /></el-icon>
          开始问答
        </el-button>
        <el-button
          v-if="canEditDataset"
          @click="showEditDialog = true"
        >
          <el-icon><Edit /></el-icon>
          编辑
        </el-button>
        <el-dropdown
          trigger="click"
          style="margin-left: 8px"
        >
          <el-button type="success">
            <el-icon><Upload /></el-icon>
            导入
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push(`/datasets/${id}/documents/upload`)">
                <el-icon><Document /></el-icon>
                上传文档
              </el-dropdown-item>
              <el-dropdown-item @click="router.push(`/datasets/${id}/documents/import-wechat`)">
                <el-icon><ChatDotRound /></el-icon>
                导入微信聊天记录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <div
      v-if="pageLoading"
      class="loading"
    >
      <LoadingSpinner text="加载中..." />
    </div>

    <div
      v-else-if="!datasetStore.currentDataset"
      class="error"
    >
      <el-empty :description="loadError || '无法加载知识库信息'">
        <el-button
          type="primary"
          @click="loadDatasetDetail(0)"
        >
          重试加载
        </el-button>
      </el-empty>
    </div>

    <template v-else>
      <el-row
        v-if="!showDocumentList"
        :gutter="20"
        class="detail-meta-row"
      >
        <el-col :span="16">
          <el-card class="info-card">
            <template #header>
              <span>基本信息</span>
            </template>
            <el-descriptions
              :column="2"
              border
            >
              <el-descriptions-item label="名称">
                {{ datasetStore.currentDataset.name }}
              </el-descriptions-item>
              <el-descriptions-item label="文档数量">
                {{ datasetStore.currentDataset.document_count }}
              </el-descriptions-item>
              <el-descriptions-item
                label="描述"
                :span="2"
              >
                {{ datasetStore.currentDataset.description || '暂无' }}
              </el-descriptions-item>
              <el-descriptions-item label="创建时间">
                {{ formatDateTime(datasetStore.currentDataset.created_at) }}
              </el-descriptions-item>
              <el-descriptions-item label="更新时间">
                {{ formatDateTime(datasetStore.currentDataset.updated_at) }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>

          <el-card
            class="info-card"
            style="margin-top: 20px"
          >
            <template #header>
              <span>配置信息</span>
            </template>
            <el-descriptions
              :column="2"
              border
            >
              <el-descriptions-item label="Embedding模型">
                {{ datasetStore.currentDataset.config.embedding_model }}
              </el-descriptions-item>
              <el-descriptions-item label="检索模型">
                {{ retrievalModelLabel }}
              </el-descriptions-item>
              <el-descriptions-item label="块大小">
                {{ datasetStore.currentDataset.config.chunk_size }}
              </el-descriptions-item>
              <el-descriptions-item label="块重叠">
                {{ datasetStore.currentDataset.config.chunk_overlap }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <el-col :span="8">
          <el-card class="info-card">
            <template #header>
              <span>统计信息</span>
            </template>
            <div class="statistics">
              <div class="stat-item">
                <div class="stat-value">
                  {{ datasetStore.currentDataset.statistics?.total_documents || 0 }}
                </div>
                <div class="stat-label">
                  总文档数
                </div>
              </div>
              <div class="stat-item success">
                <div class="stat-value">
                  {{ datasetStore.currentDataset.statistics?.indexed_documents || 0 }}
                </div>
                <div class="stat-label">
                  已索引
                </div>
              </div>
              <div class="stat-item warning">
                <div class="stat-value">
                  {{ datasetStore.currentDataset.statistics?.pending_documents || 0 }}
                </div>
                <div class="stat-label">
                  处理中
                </div>
              </div>
              <div class="stat-item danger">
                <div class="stat-value">
                  {{ datasetStore.currentDataset.statistics?.failed_documents || 0 }}
                </div>
                <div class="stat-label">
                  失败
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <section
        v-if="showDocumentList"
        id="dataset-documents"
        class="detail-documents"
      >
        <DocumentListView embed />
      </section>
    </template>

    <el-dialog
      v-model="showEditDialog"
      title="编辑知识库"
      width="500px"
    >
      <el-form
        :model="editForm"
        label-width="100px"
      >
        <el-form-item label="名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="editForm.description"
            type="textarea"
            :rows="3"
          />
        </el-form-item>
        <el-form-item label="块大小">
          <el-input-number
            v-model="editForm.config.chunk_size"
            :min="100"
            :max="2000"
            :step="100"
          />
        </el-form-item>
        <el-form-item label="块重叠">
          <el-input-number
            v-model="editForm.config.chunk_overlap"
            :min="0"
            :max="500"
            :step="10"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="editLoading"
          @click="handleUpdate"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDatasetStore } from '@/stores/dataset'
import { ArrowLeft, ArrowDown, ChatDotRound, Edit, Document, Upload } from '@element-plus/icons-vue'
import { formatDateTime } from '@/utils/format'
import { usePermission } from '@/composables/usePermission'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import DocumentListView from '@/views/document/DocumentListView.vue'
import { ElMessage, ElEmpty } from 'element-plus'

const route = useRoute()
const router = useRouter()
const datasetStore = useDatasetStore()
const { canEditDataset } = usePermission()

const id = computed(() => route.params.id as string)
/** 从知识库卡片进入时默认只看基本信息，点此按钮再拉文档列表 */
const showDocumentList = ref(false)
const showEditDialog = ref(false)
const editLoading = ref(false)
const pageLoading = ref(true)
const loadError = ref('')

const editForm = reactive({
  name: '',
  description: '',
  config: {
    chunk_size: 500,
    chunk_overlap: 50
  }
})

const retrievalModelLabel = computed(() => {
  const map: Record<string, string> = {
    semantic: '语义检索',
    full_text: '全文检索',
    hybrid: '混合检索'
  }
  return map[datasetStore.currentDataset?.config.retrieval_model || ''] || '-'
})

const toggleDocuments = () => {
  showDocumentList.value = !showDocumentList.value
  if (showDocumentList.value) {
    nextTick(() => {
      document.getElementById('dataset-documents')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
      })
    })
  }
}

const loadDatasetDetail = async (retryTimes: number = 5) => {
  pageLoading.value = true
  loadError.value = ''

  let result = await datasetStore.fetchDataset(id.value)
  let retriesLeft = retryTimes
  while (!result && retriesLeft > 0) {
    // 刷新后前端状态/鉴权可能晚于首个请求，做短暂退避重试避免误判空白。
    const waitMs = 300 + (retryTimes - retriesLeft) * 200
    await new Promise((resolve) => setTimeout(resolve, waitMs))
    result = await datasetStore.fetchDataset(id.value)
    retriesLeft -= 1
  }

  if (!result) {
    // 兜底：详情接口偶发失败时，用列表接口回填当前知识库，避免页面空白。
    const listRes = await datasetStore.fetchDatasets({ page: 1, page_size: 200, silent: true })
    const items = (listRes as any)?.items || (listRes as any)?.data?.items || []
    const matched = items.find((item: any) => String(item?.id || '') === String(id.value))
    if (matched) {
      datasetStore.setCurrentDataset(matched)
      loadError.value = ''
    } else {
      loadError.value = '加载知识库失败，请稍后重试'
    }
  }
  pageLoading.value = false
}

watch(id, async () => {
  showDocumentList.value = false
  await loadDatasetDetail(2)
}, { immediate: true })

const handleUpdate = async () => {
  editLoading.value = true
  try {
    await datasetStore.updateDataset(id.value, editForm)
    ElMessage.success('更新成功')
    showEditDialog.value = false
    datasetStore.fetchDataset(id.value)
  } catch (e) {
    // error handled by interceptor
  } finally {
    editLoading.value = false
  }
}
</script>

<style scoped lang="scss">
.dataset-detail-view {
  --card-bg: rgba(255, 255, 255, 0.9);
  --card-border: rgba(148, 163, 184, 0.2);

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

    .header-right {
      display: flex;
      gap: 12px;

      .el-button {
        border-radius: 10px;
      }
    }
  }

  .loading {
    padding: 60px 0;
  }

  .info-card {
    border-radius: 16px;
    border: 1px solid var(--card-border);
    background: var(--card-bg);
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
    backdrop-filter: blur(8px);
  }

  .detail-documents {
    margin-top: 24px;
    scroll-margin-top: 88px;
  }

  .detail-meta-row {
    margin-top: 0;
  }

  .statistics {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;

    .stat-item {
      text-align: center;
      padding: 20px;
      background: rgba(124, 77, 200, 0.06);
      border: 1px solid rgba(148, 163, 184, 0.18);
      border-radius: 12px;

      .stat-value {
        font-size: 28px;
        font-weight: 600;
        color: #303133;
      }

      .stat-label {
        margin-top: 8px;
        font-size: 14px;
        color: var(--el-text-color-secondary);
      }

      &.success .stat-value {
        color: #67c23a;
      }

      &.warning .stat-value {
        color: #e6a23c;
      }

      &.danger .stat-value {
        color: #f56c6c;
      }
    }
  }
}

:global(html.dark) .dataset-detail-view {
  --card-bg: rgba(30, 41, 59, 0.72);
  --card-border: rgba(148, 163, 184, 0.2);
}
</style>
