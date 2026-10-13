<template>
  <div class="document-upload-view">
    <div class="header">
      <div class="header-left">
        <el-button
          text
          @click="router.push(`/datasets/${datasetId}`)"
        >
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <h1>上传文档</h1>
      </div>
    </div>

    <el-card class="upload-card">
      <el-upload
        ref="uploadRef"
        drag
        :auto-upload="false"
        :on-change="handleFileChange"
        :file-list="uploadFileList"
        accept=".pdf,.docx,.doc,.txt,.md,.xlsx,.xls,.html,.epub,.png,.jpg,.jpeg,.webp,.bmp,.gif"
        multiple
      >
        <el-icon class="upload-icon">
          <UploadFilled />
        </el-icon>
        <div class="upload-text">
          <span>将文件拖到此处，或</span>
          <em>点击上传</em>
        </div>
        <template #tip>
          <div class="upload-tip">
            支持 PDF、DOCX、TXT、MD、Excel、HTML、EPUB、PNG/JPG/WEBP 图片（自动 OCR），单个文件不超过 50MB
          </div>
        </template>
      </el-upload>

      <div
        v-if="fileList.length > 0"
        class="file-list"
      >
        <h3>待上传文件 ({{ fileList.length }})</h3>
        <el-table :data="fileList">
          <el-table-column
            prop="name"
            label="文件名"
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
            label="操作"
            width="80"
          >
            <template #default="{ $index }">
              <el-button
                link
                type="danger"
                @click="handleRemoveFile($index)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <el-divider />

      <h3>处理规则</h3>
      <el-form
        :model="processRule"
        label-width="120px"
      >
        <el-form-item label="处理模式">
          <el-radio-group v-model="processRule.mode">
            <el-radio value="automatic">
              自动
            </el-radio>
            <el-radio value="custom">
              自定义
            </el-radio>
          </el-radio-group>
        </el-form-item>

        <template v-if="processRule.mode === 'custom'">
          <el-form-item label="块大小">
            <el-input-number
              v-model="processRule.rules.chunk_size"
              :min="100"
              :max="2000"
              :step="100"
            />
          </el-form-item>
          <el-form-item label="块重叠">
            <el-input-number
              v-model="processRule.rules.chunk_overlap"
              :min="0"
              :max="500"
              :step="10"
            />
          </el-form-item>
        </template>
      </el-form>

      <div class="actions">
        <el-button @click="router.push(`/datasets/${datasetId}`)">
          取消
        </el-button>
        <el-button
          type="primary"
          :loading="uploading"
          :disabled="fileList.length === 0"
          @click="handleUpload"
        >
          开始上传
        </el-button>
        <el-button
          v-if="failedFiles.length > 0"
          type="warning"
          :loading="retrying"
          :disabled="uploading"
          @click="handleRetryFailed"
        >
          重试失败 ({{ failedFiles.length }})
        </el-button>
      </div>

      <div
        v-if="uploadResults.length > 0 || uploading"
        class="upload-results"
      >
        <div class="results-heading">
          <h3>处理结果</h3>
          <span class="results-summary">已入库 {{ successCount }} · 处理中 {{ processingCount }} · 失败 {{ failedCount }}</span>
          <el-button v-if="processingCount > 0" link type="primary" :loading="refreshing" @click="refreshProcessingStatus">
            刷新处理状态
          </el-button>
        </div>
        
        <el-progress
          v-if="uploading"
          :percentage="uploadProgress"
          :status="failedCount > 0 ? 'exception' : undefined"
          style="margin-bottom: 16px;"
        />

        <el-table
          :data="uploadResults"
          max-height="400"
        >
          <el-table-column
            prop="name"
            label="文件名"
            min-width="250"
            show-overflow-tooltip
          />
          <el-table-column
            prop="status"
            label="状态"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                v-if="row.status === 'uploading'"
                type="info"
              >
                上传中
              </el-tag>
              <el-tag
                v-else-if="row.status === 'retrying'"
                type="warning"
              >
                重试中
              </el-tag>
              <el-tag v-else-if="row.status === 'processing'" type="warning">
                解析入库中
              </el-tag>
              <el-tag
                v-else-if="row.success"
                type="success"
              >
                成功
              </el-tag>
              <el-tag
                v-else
                type="danger"
              >
                失败
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="message"
            label="信息"
            min-width="150"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <span
                v-if="row.attempts > 1"
                class="attempt-info"
              >
                第{{ row.attempts }}次尝试
              </span>
              {{ row.message }}
            </template>
          </el-table-column>
          <el-table-column
            label="操作"
            width="100"
            fixed="right"
          >
            <template #default="{ row, $index }">
              <el-button
                v-if="row.documentId && row.status === 'success'"
                link
                type="primary"
                size="small"
                @click="router.push(`/documents/${row.documentId}/read`)"
              >
                打开阅读台
              </el-button>
              <el-button
                v-else-if="!row.success && row.status === 'failed' && !uploading && !retrying && row.file"
                link
                type="primary"
                size="small"
                @click="handleRetrySingle($index)"
              >
                重试
              </el-button>
              <span v-else-if="row.status === 'uploading' || row.status === 'retrying'">
                <el-icon class="is-loading"><Loading /></el-icon>
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  uploadDocumentWithRetry,
  createConcurrentUploader,
  getDocument,
  getDocuments,
  isValidDatasetIdForApi
} from '@/api/document'
import { ArrowLeft, UploadFilled, Loading } from '@element-plus/icons-vue'
import { formatFileSize } from '@/utils/format'
import { ElMessage } from 'element-plus'
import type { UploadRawFile } from 'element-plus'
import type { Document } from '@/types/document'

const route = useRoute()
const router = useRouter()

const datasetId = computed(() => {
  const raw = route.params.id
  if (Array.isArray(raw)) return String(raw[0] ?? '')
  return String(raw ?? '')
})
const uploadRef = ref()
const fileList = ref<File[]>([])
const uploadFileList = ref<any[]>([])
const uploading = ref(false)
const retrying = ref(false)
const refreshing = ref(false)
const existingDocuments = ref<string[]>([])

interface UploadResult {
  name: string
  file: File | null
  documentId?: string
  success: boolean
  status: 'pending' | 'uploading' | 'retrying' | 'processing' | 'success' | 'failed'
  message: string
  attempts: number
}

const uploadResults = ref<UploadResult[]>([])

const processRule = reactive({
  mode: 'automatic' as 'automatic' | 'custom',
  rules: {
    chunk_size: 500,
    chunk_overlap: 50
  }
})

const successCount = computed(() => uploadResults.value.filter(r => r.success).length)
const processingCount = computed(() => uploadResults.value.filter(r => r.status === 'processing').length)
const failedCount = computed(() => uploadResults.value.filter(r => r.status === 'failed').length)
const failedFiles = computed(() => uploadResults.value.filter(r => r.status === 'failed'))
const uploadProgress = computed(() => {
  if (uploadResults.value.length === 0) return 0
  const completed = uploadResults.value.filter(r => r.status === 'success' || r.status === 'failed').length
  return Math.round((completed / uploadResults.value.length) * 100)
})

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

const unwrapDocument = (response: any): Document | null => {
  const payload = response?.data?.data ?? response?.data ?? response
  return payload && typeof payload === 'object' ? payload as Document : null
}

const waitForDocumentReady = async (result: UploadResult, documentId: string) => {
  result.documentId = documentId
  result.status = 'processing'
  result.message = '文件已接收，正在解析、切片并建立索引...'

  const deadline = Date.now() + 60000
  while (Date.now() < deadline) {
    try {
      const document = unwrapDocument(await getDocument(documentId))
      if (document?.status === 'completed') {
        result.success = true
        result.status = 'success'
        result.message = `解析并索引完成${document.segment_count ? `，已生成 ${document.segment_count} 个知识片段` : ''}`
        return
      }
      if (document?.status === 'failed') {
        result.success = false
        result.status = 'failed'
        result.message = document.error_reason || '文档处理失败，可重试上传或重新处理'
        return
      }
      const phase = document?.processing_phase
      result.message = phase === 'extracting'
        ? '正在提取原文...'
        : phase === 'chunking'
          ? '正在切分知识片段...'
          : phase === 'embedding'
            ? '正在生成向量...'
            : phase === 'indexing'
              ? '正在写入检索索引...'
              : '文件已接收，正在解析、切片并建立索引...'
    } catch (error) {
      // 单次状态查询失败不应把已上传的文档误报成上传失败，下一轮继续查询。
      console.warn('查询文档处理状态失败:', error)
    }
    await sleep(1500)
  }

  result.status = 'processing'
  result.success = false
  result.message = '已上传，后台仍在处理中；可点击“刷新处理状态”继续查看'
}

const refreshProcessingStatus = async () => {
  const pending = uploadResults.value.filter(result => result.status === 'processing' && result.documentId)
  if (!pending.length) return
  refreshing.value = true
  try {
    await Promise.all(pending.map(result => waitForDocumentReady(result, result.documentId!)))
  } finally {
    refreshing.value = false
  }
}

const loadExistingDocuments = async () => {
  if (!isValidDatasetIdForApi(datasetId.value)) return
  try {
    const response = await getDocuments(datasetId.value)
    existingDocuments.value = response.data?.items.map((doc: Document) => doc.name) || []
  } catch (e) {
    console.error('加载文档列表失败:', e)
  }
}

const isFileExists = (fileName: string): boolean => {
  const inUploadList = fileList.value.some(file => file.name === fileName)
  const inExistingDocs = existingDocuments.value.includes(fileName)
  const inResults = uploadResults.value.some(r => r.name === fileName && r.success)
  return inUploadList || inExistingDocs || inResults
}

const handleFileChange = (file: any) => {
  if (!file?.raw) {
    ElMessage.warning('无效的文件对象')
    return
  }
  
  if (isFileExists(file.raw.name)) {
    ElMessage.warning(`文件 "${file.raw.name}" 已经上传过或在上传列表中，请勿重复上传`)
    return
  }
  fileList.value.push(file.raw)
  uploadFileList.value.push(file)
}

onMounted(() => {
  loadExistingDocuments()
})

const handleRemoveFile = (index: number) => {
  const removed = fileList.value[index]
  const removedName = removed?.name || ''
  fileList.value.splice(index, 1)
  uploadFileList.value.splice(index, 1)
  if (removedName) {
    const resultIndex = uploadResults.value.findIndex(r => r.name === removedName)
    if (resultIndex !== -1) {
      uploadResults.value.splice(resultIndex, 1)
    }
  }
}

const uploadSingleFile = async (
  file: File | null | undefined,
  result: UploadResult,
  uploader: ReturnType<typeof createConcurrentUploader>,
  maxRetries: number
): Promise<void> => {
  if (!file) {
    if (result) {
      result.success = false
      result.status = 'failed'
      result.message = '文件对象丢失，请重新选择文件'
    }
    return
  }

  if (!result) {
    console.error('uploadSingleFile: result 为空', { fileName: file.name })
    return
  }

  result.status = 'uploading'
  
  try {
    const response = await uploader.add(() =>
      uploadDocumentWithRetry(
        datasetId.value,
        file,
        processRule.mode === 'custom' ? processRule : undefined,
        {
          maxRetries,
          baseDelay: 1000,
          onRetry: (attempt) => {
            result.status = 'retrying'
            result.attempts = attempt
            result.message = `第${attempt}次重试...`
          }
        }
      )
    )
    
    const document = unwrapDocument(response)
    if (!document?.id) {
      result.success = false
      result.status = 'failed'
      result.message = '上传接口未返回文档 ID，无法跟踪处理状态'
      throw new Error(result.message)
    }
    await waitForDocumentReady(result, document.id)
    existingDocuments.value.push(file.name)
  } catch (error: any) {
    result.success = false
    result.status = 'failed'
    const errorMsg = error?.response?.data?.detail || error?.message || '上传失败'
    result.message = errorMsg
    console.error(`文件 ${file.name} 上传失败:`, error)
    throw error
  }
}

const handleUpload = async () => {
  if (fileList.value.length === 0) return
  if (!isValidDatasetIdForApi(datasetId.value)) {
    ElMessage.error('知识库 ID 无效，请从知识库详情进入上传页')
    return
  }

  uploading.value = true
  retrying.value = false
  
  uploadResults.value = fileList.value.map(file => ({
    name: file.name,
    file: file,
    success: false,
    status: 'pending' as const,
    message: '等待上传',
    attempts: 0
  }))

  // SQLite 下多路并发上传易触发 database is locked，改为单路更稳
  const uploader = createConcurrentUploader(1)

  const uploadPromises = uploadResults.value.map(result =>
    uploadSingleFile(result.file, result, uploader, 3).catch(e => {
      console.error('上传异常:', e)
    })
  )

  try {
    await Promise.all(uploadPromises)
  } catch (e) {
    console.error('批量上传过程中发生错误:', e)
  }

  await uploader.waitForAll()
  uploading.value = false

  if (uploadResults.value.every(r => r.success)) {
    ElMessage.success('全部上传成功')
  } else if (uploadResults.value.some(r => r.success)) {
    ElMessage.warning(`部分文件上传失败 (${failedCount.value}/${uploadResults.value.length})`)
  } else {
    ElMessage.error('全部上传失败')
  }
}

const handleRetryFailed = async () => {
  if (failedFiles.value.length === 0) return

  retrying.value = true
  const uploader = createConcurrentUploader(1)

  const failedResults = uploadResults.value.filter(r => r.status === 'failed' && r.file)
  
  for (const result of failedResults) {
    result.status = 'retrying'
    result.message = '重试中...'
    result.attempts = 0
    
    uploadSingleFile(result.file, result, uploader, 3).catch(e => {
      console.error('重试异常:', e)
    })
  }

  await uploader.waitForAll()
  retrying.value = false

  if (failedCount.value === 0) {
    ElMessage.success('全部重试成功')
  } else {
    ElMessage.warning(`仍有 ${failedCount.value} 个文件上传失败`)
  }
}

const handleRetrySingle = async (index: number) => {
  const result = uploadResults.value[index]
  
  if (!result) {
    ElMessage.error('找不到对应的上传记录')
    return
  }
  
  if (result.success) {
    ElMessage.warning('该文件已上传成功')
    return
  }
  
  if (!result.file) {
    ElMessage.error('该文件的原始数据已丢失，请重新选择文件上传')
    return
  }

  result.status = 'retrying'
  result.message = '重试中...'
  result.attempts = 0

  const uploader = createConcurrentUploader(1)
  
  try {
    await uploadSingleFile(result.file, result, uploader, 3)
    
    if (result.success) {
      ElMessage.success(`${result.name} 重试成功`)
    } else {
      ElMessage.error(`${result.name} 重试失败: ${result.message}`)
    }
  } catch (e) {
    console.error('重试失败:', e)
    ElMessage.error(`${result.name} 重试失败`)
  }
}
</script>

<style scoped lang="scss">
.document-upload-view {
  max-width: 900px;
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
  }

  .upload-card {
    border-radius: 16px;
    border: 1px solid var(--card-border);
    background: var(--card-bg);
    box-shadow: 0 12px 24px rgba(15, 23, 42, 0.07);
    backdrop-filter: blur(8px);

    :deep(.el-upload-dragger) {
      border-radius: 12px;
      border-color: rgba(124, 77, 200, 0.32);
      background: rgba(124, 77, 200, 0.04);
    }

    .upload-icon {
      font-size: 67px;
      color: #704ac6;
      margin-bottom: 16px;
    }

    .upload-text {
      color: #606266;
      em {
        color: #704ac6;
        font-style: normal;
      }
    }

    .upload-tip {
      margin-top: 8px;
      font-size: 12px;
      color: #827a90;
    }

    .file-list {
      margin-top: 20px;

      h3 {
        margin: 0 0 12px;
        font-size: 16px;
        font-weight: 600;
      }
    }

    h3 {
      margin: 20px 0 12px;
      font-size: 16px;
      font-weight: 600;
    }

    .actions {
      margin-top: 20px;
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      flex-wrap: wrap;

      .el-button {
        border-radius: 10px;
      }
    }

    .upload-results {
      margin-top: 24px;

      .results-heading {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }

      h3 {
        margin: 0 0 16px;
        font-size: 16px;
        font-weight: 600;
      }

      .results-summary {
        margin-right: auto;
        color: #827a90;
        font-size: 12px;
      }

      .attempt-info {
        color: #E6A23C;
        font-size: 12px;
        margin-right: 4px;
      }
    }
  }
}

:global(html.dark) .document-upload-view {
  --card-bg: rgba(30, 41, 59, 0.72);
  --card-border: rgba(148, 163, 184, 0.2);
}
</style>
